/*
 *
 * Licensed to the Apache Software Foundation (ASF) under one
 * or more contributor license agreements.  See the NOTICE file
 * distributed with this work for additional information
 * regarding copyright ownership.  The ASF licenses this file
 * to you under the Apache License, Version 2.0 (the
 * "License"); you may not use this file except in compliance
 * with the License.  You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing,
 * software distributed under the License is distributed on an
 * "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
 * KIND, either express or implied.  See the License for the
 * specific language governing permissions and limitations
 * under the License.
 *
 */

#include <proton/codec.h>
#include <proton/delivery.h>
#include <proton/engine.h>
#include <proton/event.h>
#include <proton/listener.h>
#include <proton/message.h>
#include <proton/proactor.h>
#include <proton/sasl.h>
#include <proton/ssl.h>
#include <proton/types.h>
#include <proton/version.h>

#include <memory.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <inttypes.h>

static const pn_bytes_t SEND_TIME = { sizeof("SendTime") - 1, "SendTime" };

typedef enum { CLIENT, SERVER } connection_mode;
const char* connection_mode_names[] = { "client", "server", NULL };

typedef enum { ACTIVE, PASSIVE } channel_mode;
const char* channel_mode_names[] = { "active", "passive", NULL };

typedef enum { SEND, RECEIVE } operation;
const char* operation_names[] = { "send", "receive", NULL };

struct arrow {
    connection_mode connection_mode;
    channel_mode channel_mode;
    operation operation;
    const char* id;
    const char* scheme;
    const char* host;
    const char* port;
    const char* path;
    const char* username;
    const char* password;
    const char* cert;
    const char* key;
    bool tls;
    uint32_t desired_duration;
    size_t desired_count;
    size_t body_size;
    size_t credit_window;
    bool durable;
    bool settlement;

    pn_proactor_t* proactor;
    pn_listener_t* listener;
    pn_connection_t* connection;
    pn_message_t* message;
    pn_rwbytes_t buffer; // Encoded message buffer

    time_t start_time;
    size_t sent;
    size_t received;
    size_t acknowledged;
    pn_ssl_domain_t *ssl_domain;
};

void fail_(const char* file, int line, const char* fmt, ...) {
    fprintf(stderr, "%s:%d: ", file, line);
    va_list ap;
    va_start(ap, fmt);
    vfprintf(stderr, fmt, ap);
    va_end(ap);
    fprintf(stderr, "\n");
    fflush(stderr);
    exit(1);
}

#define FAIL(...) fail_(__FILE__, __LINE__, __VA_ARGS__)
#define ASSERT(EXPR) ((EXPR) ? (void)0 : FAIL("Failed assertion: %s", #EXPR))

void eprint(const char* fmt, ...) {
    va_list ap;
    va_start(ap, fmt);
    vfprintf(stderr, fmt, ap);
    va_end(ap);
    fprintf(stderr, "\n");
    fflush(stderr);
}

static void stop(struct arrow* a) {
    if (a->connection) {
        pn_connection_close(a->connection);
    }

    if (a->listener) {
        pn_listener_close(a->listener);
    }

    pn_proactor_cancel_timeout(a->proactor);
}

static inline bool bytes_equal(const pn_bytes_t a, const pn_bytes_t b) {
    return (a.size == b.size && !memcmp(a.start, b.start, a.size));
}

// TODO aconway 2017-06-09: need windows portable version
int64_t now() {
    struct timespec t;
    clock_gettime(CLOCK_REALTIME, &t);
    return t.tv_sec * 1000 + t.tv_nsec / (1000 * 1000);
}

static const size_t BUF_MIN = 1024;

// Ensure buf has at least size bytes, use realloc if need be
static void ensure(pn_rwbytes_t* buf, size_t size) {
    if (buf->size < size) {
        buf->start = realloc(buf->start, size);
        buf->size = size;
    }
}

// Encode message m into buffer buf, return the size.  The buffer is
// expanded using realloc() if needed.
static size_t encode_message(pn_message_t* m, pn_rwbytes_t* buf) {
    int err = 0;
    ensure(buf, BUF_MIN);
    size_t size = buf->size;
    while ((err = pn_message_encode(m, buf->start, &size)) != 0) {
        if (err == PN_OVERFLOW) {
            ensure(buf, buf->size * 2);
            size = buf->size;
        } else if (err != 0) {
            FAIL("Error encoding message: %s %s", pn_code(err), pn_error_text(pn_message_error(m)));
        }
    }
    return size;
}

// Decode message from delivery d into message m.  Use buf to hold the
// message data, expand with realloc() if needed.
static void decode_message(pn_message_t* m, pn_delivery_t* d, pn_rwbytes_t* buf) {
    pn_link_t* l = pn_delivery_link(d);
    ssize_t size = pn_delivery_pending(d);
    ensure(buf, size);
    ASSERT(size == pn_link_recv(l, buf->start, size));
    pn_message_clear(m);
    if (pn_message_decode(m, buf->start, size)) {
        FAIL("pn_message_decode: %s", pn_error_text(pn_message_error(m)));
    }
}

static void print_message(pn_message_t* m) {
    pn_atom_t id_atom = pn_message_get_id(m);
    ASSERT(id_atom.type == PN_STRING);
    pn_bytes_t id = id_atom.u.as_bytes;
    pn_data_t* props = pn_message_properties(m);
    pn_data_rewind(props);
    ASSERT(pn_data_next(props));
    ASSERT(pn_data_get_map(props) == 2);
    ASSERT(pn_data_enter(props));
    ASSERT(pn_data_next(props));
    ASSERT(pn_data_type(props) == PN_STRING);
    pn_bytes_t key = pn_data_get_string(props);
    if (!bytes_equal(key, SEND_TIME)) {
        FAIL("Unexpected property name: %.*s", key.start, key.size);
    }
    ASSERT(pn_data_next(props));
    ASSERT(pn_data_type(props) == PN_LONG);
    int64_t stime = pn_data_get_long(props);
    ASSERT(pn_data_exit(props));
    printf("%s,%" PRId64 ",%" PRId64 "\n", id.start, stime, now());
}

static void send_message(struct arrow* a, pn_link_t* l) {
    a->sent++;
    int64_t stime = now();
    pn_atom_t id_atom;
    int id_len = snprintf(NULL, 0, "%zu", a->sent);
    char id_str[id_len + 1];
    snprintf(id_str, id_len + 1, "%zu", a->sent);
    id_atom.type = PN_STRING;
    id_atom.u.as_bytes = pn_bytes(id_len + 1, id_str);
    pn_message_set_id(a->message, id_atom);
    pn_data_t* props = pn_message_properties(a->message);
    pn_data_clear(props);
    ASSERT(!pn_data_put_map(props));
    ASSERT(pn_data_enter(props));
    ASSERT(!pn_data_put_string(props, pn_bytes(SEND_TIME.size, SEND_TIME.start)));
    ASSERT(!pn_data_put_long(props, stime));
    ASSERT(pn_data_exit(props));
    size_t size = encode_message(a->message, &a->buffer);
    ASSERT(size > 0);
    // Use id as unique delivery tag
    pn_delivery(l, pn_dtag((const char* )&a->sent, sizeof(a->sent)));
    ASSERT(size == pn_link_send(l, a->buffer.start, size));
    ASSERT(pn_link_advance(l));
    printf("%s,%" PRId64 "\n", id_str, stime);
}

static void fail_if_condition(pn_event_t* e, pn_condition_t* cond) {
    if (pn_condition_is_set(cond)) {
        FAIL("%s: %s: %s", pn_event_type_name(pn_event_type(e)),
             pn_condition_get_name(cond), pn_condition_get_description(cond));
    }
}

static bool handle(struct arrow* a, pn_event_t* e) {
    switch (pn_event_type(e)) {
    case PN_LISTENER_OPEN:
        // TODO aconway 2017-06-12: listening notice
        // printf("listening\n");
        // fflush(stdout);
        break;

    case PN_LISTENER_ACCEPT:
        a->connection = pn_connection();
        pn_listener_accept(pn_event_listener(e), a->connection);
        break;

    case PN_CONNECTION_INIT:
        pn_connection_set_container(pn_event_connection(e), a->id);
        if (a->channel_mode == ACTIVE) {
            if (a->username) {
                pn_connection_set_user(pn_event_connection(e), a->username);
            }
            if (a->password) {
                pn_connection_set_password(pn_event_connection(e), a->password);
            }

            if (a->host) {
                bool has_port = a->port && strlen(a->port) > 0;
                char domain[strlen(a->host) + (has_port ? (strlen(a->port) + 1) : 0) + 1];
                sprintf(domain, (has_port ? "%s:%s" : "%s"), a->host, a->port);
                pn_connection_set_hostname(pn_event_connection(e), domain);
            }

            pn_session_t* ssn = pn_session(pn_event_connection(e));
            pn_session_open(ssn);
            pn_link_t* l = NULL;
            switch (a->operation) {
            case SEND:
                l = pn_sender(ssn, "arrow");
                pn_terminus_set_address(pn_link_target(l), a->path);
                // At-least-once: send unsettled, receiver settles first
                pn_link_set_snd_settle_mode(l, PN_SND_UNSETTLED);
                pn_link_set_rcv_settle_mode(l, PN_RCV_FIRST);
                break;
            case RECEIVE:
                l = pn_receiver(ssn, "arrow");
                pn_terminus_set_address(pn_link_source(l), a->path);
                break;
            }
            pn_link_open(l);
        }
        break;

    case PN_CONNECTION_BOUND: {
        // Turn off security
        pn_transport_t* t = pn_event_transport(e);

        if (a->tls) {
            int err =  pn_ssl_init(pn_ssl(t), a->ssl_domain, NULL);
            if (err) {
                FAIL("error initializing SSL: %s\n", pn_code(err));
            }
        }

        bool require_auth = a->username || a->password;
        pn_transport_require_auth(t, require_auth);
        if (!require_auth) {
            pn_sasl_allowed_mechs(pn_sasl(t), "ANONYMOUS");
        } else {
            pn_sasl_set_allow_insecure_mechs(pn_sasl(t), true);
        }
        break;
    }
    case PN_CONNECTION_REMOTE_OPEN: {
        pn_connection_open(pn_event_connection(e)); // Return the open if not already done
        break;
    }
    case PN_SESSION_REMOTE_OPEN:
        pn_session_open(pn_event_session(e));
        break;

    case PN_LINK_REMOTE_OPEN: {
        pn_link_t* l = pn_event_link(e);
        pn_terminus_t* t = pn_link_target(l);
        pn_terminus_t* rt = pn_link_remote_target(l);
        pn_terminus_set_address(t, pn_terminus_get_address(rt));
        pn_link_open(l);
        if (pn_link_is_receiver(l)) {
            pn_link_flow(l, a->credit_window);
        }
        break;
    }
    case PN_LINK_FLOW: {
        pn_link_t* link = pn_event_link(e);

        if (pn_link_is_sender(link)) {
            while (pn_link_credit(link) > 0) {
                if (a->desired_count > 0 && a->sent == a->desired_count) {
                    break;
                }

                send_message(a, link);
            }
        }

        break;
    }
    case PN_DELIVERY: {
        pn_delivery_t* delivery = pn_event_delivery(e);
        pn_link_t* link = pn_delivery_link(delivery);

        if (pn_link_is_sender(link)) {
            // Message acknowledged

            pn_delivery_settle(delivery);

            if (a->settlement) {
                pn_delivery_tag_t dtag = pn_delivery_tag(delivery);
                ASSERT(dtag.size == 8);
                uint8_t* p = (uint8_t*)dtag.start;
                if ((a->acknowledged & 255) == 0) {
                    int64_t tag = 0;
                    for (int i=0; i<64; i+=8) {
                        tag |= *p++ << i;
                    }
                    printf("S%" PRId64 ",%" PRId64 "\n", tag, now());
                }
            }

            a->acknowledged++;

            if (a->acknowledged == a->desired_count) {
                stop(a);
                break;
            }
        } else if (pn_link_is_receiver(link)) {
            if (!pn_delivery_readable(delivery) || pn_delivery_partial(delivery)) {
                break;
            }

            // Message received

            decode_message(a->message, delivery, &a->buffer);
            print_message(a->message);

            pn_delivery_update(delivery, PN_ACCEPTED);
            pn_delivery_settle(delivery);

            a->received++;

            if (a->received == a->desired_count) {
                stop(a);
                break;
            }

            pn_link_flow(link, a->credit_window - pn_link_credit(link));
        } else {
            FAIL("Unexpected");
        }

        break;
    }
    case PN_TRANSPORT_CLOSED:
        // On server, ignore errors from dummy connections used to
        // test if we are listening

        if (a->connection_mode == CLIENT) {
            fail_if_condition(e, pn_transport_condition(pn_event_transport(e)));
        }

        break;

    case PN_CONNECTION_REMOTE_CLOSE:
        fail_if_condition(e, pn_connection_remote_condition(pn_event_connection(e)));
        pn_connection_close(pn_event_connection(e));
        break;

    case PN_SESSION_REMOTE_CLOSE:
        fail_if_condition(e, pn_session_remote_condition(pn_event_session(e)));
        pn_session_close(pn_event_session(e));
        break;

    case PN_LINK_REMOTE_CLOSE:
        fail_if_condition(e, pn_link_remote_condition(pn_event_link(e)));
        pn_link_close(pn_event_link(e));
        break;

    case PN_LISTENER_CLOSE:
        fail_if_condition(e, pn_listener_condition(pn_event_listener(e)));
        break;

    case PN_PROACTOR_TIMEOUT:
        stop(a);
        break;

    case PN_PROACTOR_INACTIVE:
        return false;

    default:
        break;
    }

    return true;
}

void run(struct arrow* a) {
    if (a->desired_duration > 0) {
        pn_proactor_set_timeout(a->proactor, a->desired_duration * 1000);
    }

    while (true) {
        pn_event_batch_t* events = pn_proactor_wait(a->proactor);
        pn_event_t* e;

        for (e = pn_event_batch_next(events); e; e = pn_event_batch_next(events)) {
            if (!handle(a, e)) {
                return;
            }
        }

        pn_proactor_done(a->proactor, events);
    }
}

int token(const char* names[], const char* name) {
    size_t i = 0;
    for (; names[i] && strcmp(names[i], name); i++)
        ;
    if (!names[i]) {
        FAIL("unknown token: %s", name);
    }
    return i;
}

char* find_arg(size_t kwargc, char* kwargv[][2], char* key) {
    for (int i = 0; i < kwargc; i++) {
        if (strcmp(kwargv[i][0], key) == 0) return kwargv[i][1];
    }

    return NULL;
}

int main(size_t argc, char** argv) {
    if (argc == 1) {
        printf("Qpid Proton C %d.%d.%d\n", PN_VERSION_MAJOR, PN_VERSION_MINOR, PN_VERSION_POINT);
        return 0;
    }

    size_t kwargc = argc - 1;
    char* kwargv[kwargc][2];
    char* arg;

    for (int i = 0; i < kwargc; i++) {
        arg = strdup(argv[i + 1]);
        kwargv[i][0] = strsep(&arg, "=");
        kwargv[i][1] = arg;
    }

    if (atoi(find_arg(kwargc, kwargv, "transaction-size")) > 0) {
        FAIL("this impl doesn't support transactions");
    }

    struct arrow a = { 0 };
    a.connection_mode = (connection_mode)token(connection_mode_names, find_arg(kwargc, kwargv, "connection-mode"));
    a.channel_mode = (channel_mode)token(channel_mode_names, find_arg(kwargc, kwargv, "channel-mode"));
    a.operation = (operation)token(operation_names, find_arg(kwargc, kwargv, "operation"));
    a.id = find_arg(kwargc, kwargv, "id");
    a.scheme = find_arg(kwargc, kwargv, "scheme");
    a.host = find_arg(kwargc, kwargv, "host");
    a.port = find_arg(kwargc, kwargv, "port");
    a.path = find_arg(kwargc, kwargv, "path");
    a.username = find_arg(kwargc, kwargv, "username");
    a.password = find_arg(kwargc, kwargv, "password");
    a.cert = find_arg(kwargc, kwargv, "cert");
    a.key = find_arg(kwargc, kwargv, "key");
    a.desired_duration = atoi(find_arg(kwargc, kwargv, "duration"));
    a.desired_count = atoi(find_arg(kwargc, kwargv, "count"));
    a.body_size = atoi(find_arg(kwargc, kwargv, "body-size"));
    a.credit_window = atoi(find_arg(kwargc, kwargv, "credit-window"));
    a.durable = atoi(find_arg(kwargc, kwargv, "durable")) == 1;
    a.settlement = atoi(find_arg(kwargc, kwargv, "settlement")) == 1;
    a.ssl_domain = pn_ssl_domain(PN_SSL_MODE_CLIENT);

    if (a.scheme == NULL) {
        a.scheme = "amqp";
    }
    a.tls = strcmp(a.scheme, "amqps") == 0;

    // Set up the fixed parts of the message
    a.message = pn_message();
    pn_message_set_durable(a.message, a.durable);
    char* body = (char*)malloc(a.body_size);
    memset(body, 'x', a.body_size);
    pn_data_put_string(pn_message_body(a.message), pn_bytes(a.body_size, body));
    free(body);

    // Connect or listen
    char addr[PN_MAX_ADDR];
    pn_proactor_addr(addr, sizeof(addr), a.host, a.port);
    a.proactor = pn_proactor();

    switch (a.connection_mode) {
    case CLIENT:
        a.connection = pn_connection();
        pn_proactor_connect(a.proactor, a.connection, addr);
        if (a.tls) {
            // PN_SSL_ANONYMOUS_PEER is default
            a.ssl_domain = pn_ssl_domain(PN_SSL_MODE_CLIENT);
            if (a.cert && a.key) {
                pn_ssl_domain_set_credentials(a.ssl_domain, a.cert, a.key, NULL);
            }
        }
        break;
    case SERVER:
        a.listener = pn_listener();
        pn_proactor_listen(a.proactor, a.listener, addr, 32);
        if (a.tls) {
            FAIL("This impl can't be a server and support TLS");
        }
        break;
    }

    a.start_time = now();

    run(&a);

    if (a.ssl_domain) pn_ssl_domain_free(a.ssl_domain);
    if (a.message) pn_message_free(a.message);
    if (a.proactor) pn_proactor_free(a.proactor);
    free(a.buffer.start);

    return 0;
}
