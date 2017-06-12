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
#include <proton/types.h>
#include <proton/version.h>

#include <memory.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <inttypes.h>


static const pn_bytes_t SEND_TIME = { sizeof("SendTime")-1, "SendTime" };

typedef enum { CLIENT, SERVER } connection_mode;
const char *connection_mode_names[] = { "client", "server", NULL };

typedef enum { ACTIVE, PASSIVE } channel_mode;
const char *channel_mode_names[] = { "active", "passive", NULL };

typedef enum { SEND, RECEIVE } operation;
const char *operation_names[] = { "send", "receive", NULL };

struct arrow {
    connection_mode connection_mode;
    channel_mode channel_mode;
    operation operation;
    const char* id;
    const char* host;
    const char* port;
    const char* path;
    size_t messages;
    size_t body_size;
    size_t credit_window;
    bool durable;

    pn_proactor_t *proactor;
    pn_listener_t *listener;
    pn_connection_t *connection;
    pn_message_t *message;
    pn_rwbytes_t buffer;        /* Encoded message buffer */

    size_t sent;
    size_t received;
    size_t accepted;
};

void fail_(const char *file, int line, const char *fmt, ...) {
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
#define ASSERT(EXPR) ((EXPR) ? (void)0 : FAIL("failed assertion: %s", #EXPR))

static void stop(struct arrow* a) {
    if (a->connection) {
        pn_connection_close(a->connection);
    }
    if (a->listener) {
        pn_listener_close(a->listener);
    }
}

static inline bool bytes_equal(const pn_bytes_t a, const pn_bytes_t b) {
    return (a.size == b.size && !memcmp(a.start, b.start, a.size));
}

/* TODO aconway 2017-06-09: need windows portable version */
pn_timestamp_t timestamp() {
    struct timespec t;
    clock_gettime(CLOCK_REALTIME, &t);
    return t.tv_sec*1000 + t.tv_nsec/1000000;
}

static const size_t BUF_MIN = 1024;

/* Ensure buf has at least size bytes, use realloc if need be */
static void ensure(pn_rwbytes_t *buf, size_t size) {
    if (buf->size < size) {
        buf->start = realloc(buf->start, size);
        buf->size = size;
    }
}

/* Encode message m into buffer buf, return the size.
 * The buffer is expanded using realloc() if needed.
 */
static size_t encode_message(pn_message_t* m, pn_rwbytes_t *buf) {
    int err = 0;
    ensure(buf, BUF_MIN);
    size_t size = buf->size;
    while ((err = pn_message_encode(m, buf->start, &size)) != 0) {
        if (err == PN_OVERFLOW) {
            ensure(buf, buf->size * 2);
        } else if (err != 0) {
            FAIL("error encoding message: %s %s", pn_code(err), pn_error_text(pn_message_error(m)));
        }
    }
    return size;
}

/* Decode message from delivery d into message m.
 * Use buf to hold the message data, expand with realloc() if needed.
 */
static void decode_message(pn_message_t *m, pn_delivery_t *d, pn_rwbytes_t *buf) {
    pn_link_t *l = pn_delivery_link(d);
    ssize_t size = pn_delivery_pending(d);
    ensure(buf, size);
    ASSERT(size == pn_link_recv(l, buf->start, size));
    pn_message_clear(m);
    if (pn_message_decode(m, buf->start, size)) {
        FAIL("pn_message_decode: %s", pn_error_text(pn_message_error(m)));
    }
}

static void print_message(pn_message_t *m) {
    pn_atom_t id_atom = pn_message_get_id(m);
    ASSERT(id_atom.type == PN_ULONG);
    uint64_t id = id_atom.u.as_ulong;

    pn_data_t *props = pn_message_properties(m);
    pn_data_rewind(props);
    ASSERT(pn_data_next(props));
    ASSERT(pn_data_get_map(props) == 2);
    ASSERT(pn_data_enter(props));
    ASSERT(pn_data_next(props));
    ASSERT(pn_data_type(props) == PN_STRING);
    pn_bytes_t key = pn_data_get_string(props);
    if (!bytes_equal(key, SEND_TIME)) {
        FAIL("unexpected property name: %.*s", key.start, key.size);
    }
    ASSERT(pn_data_next(props));
    ASSERT(pn_data_type(props) == PN_TIMESTAMP);
    pn_timestamp_t ts = pn_data_get_timestamp(props);
    pn_data_exit(props);
    printf("%" PRIu64 ",%" PRId64 ",%" PRId64 "\n", id, ts, timestamp());
}

static void send_message(struct arrow *a, pn_link_t *l) {
    ++a->sent;
    pn_timestamp_t ts = timestamp();
    pn_atom_t id;
    id.type = PN_ULONG;
    id.u.as_ulong = (uint64_t)a->sent;
    pn_message_set_id(a->message, id);
    pn_data_t *props = pn_message_properties(a->message);
    pn_data_clear(props);
    ASSERT(!pn_data_put_map(props));
    ASSERT(pn_data_enter(props));
    ASSERT(!pn_data_put_string(props, pn_bytes(SEND_TIME.size, SEND_TIME.start)));
    ASSERT(!pn_data_put_timestamp(props, ts));
    ASSERT(pn_data_exit(props));
    size_t size = encode_message(a->message, &a->buffer);
    ASSERT(size > 0);
    /* Use id as unique delivery tag. */
    pn_delivery(l, pn_dtag((const char *)&a->sent, sizeof(a->sent)));
    ASSERT(size == pn_link_send(l, a->buffer.start, size));
    ASSERT(pn_link_advance(l));
    printf("%zu,%" PRId64 "\n", a->sent, ts);
}

static void fail_if_condition(pn_event_t *e, pn_condition_t *cond) {
    if (pn_condition_is_set(cond)) {
        FAIL("%s: %s: %s", pn_event_type_name(pn_event_type(e)),
             pn_condition_get_name(cond), pn_condition_get_description(cond));
    }
}

static bool handle(struct arrow* a, pn_event_t* e) {
    switch (pn_event_type(e)) {

    case PN_LISTENER_OPEN:
        /* TODO aconway 2017-06-12: listening notice */
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
            pn_session_t *ssn = pn_session(pn_event_connection(e));
            pn_session_open(ssn);
            pn_link_t *l = NULL;
            switch (a->operation) {
            case SEND:
                l = pn_sender(ssn, "arrow");
                pn_terminus_set_address(pn_link_target(l), a->path);
                /* At-least-once: send unsettled, receiver settles first */
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
        /* Turn off security */
        pn_transport_t *t = pn_event_transport(e);
        pn_transport_require_auth(t, false);
        pn_sasl_allowed_mechs(pn_sasl(t), "ANONYMOUS");
        break;
    }
    case PN_CONNECTION_REMOTE_OPEN: {
        pn_connection_open(pn_event_connection(e)); /* Return the open if not already done */
        break;
    }
    case PN_SESSION_REMOTE_OPEN:
        pn_session_open(pn_event_session(e));
        break;

    case PN_LINK_REMOTE_OPEN: {
        pn_link_t *l = pn_event_link(e);
        pn_link_open(l);
        if (pn_link_is_receiver(l)) {
            pn_link_flow(l, a->credit_window);
        }
        break;
    }
    case PN_LINK_FLOW: {
        pn_link_t *l = pn_event_link(e);
        while (pn_link_is_sender(l) && pn_link_credit(l) > 0 && a->sent < a->messages) {
            send_message(a, l);
        }
        break;
    }
    case PN_DELIVERY: {
        pn_delivery_t *d = pn_event_delivery(e);
        pn_link_t *l = pn_delivery_link(d);
        if (pn_link_is_sender(l)) { /* Message acknowledged */
            ASSERT(PN_ACCEPTED == pn_delivery_remote_state(d));
            pn_delivery_settle(d);
            if (++a->accepted >= a->messages) {
                stop(a);
            }
        } else if (pn_link_is_receiver(l) && pn_delivery_readable(d) && !pn_delivery_partial(d)) {
            decode_message(a->message, d, &a->buffer);
            print_message(a->message);
            pn_delivery_update(d, PN_ACCEPTED);
            pn_delivery_settle(d);
            if (++a->received >= a->messages) {
                stop(a);
            }
            pn_link_flow(l, a->credit_window - pn_link_credit(l));
        }
        break;
    }
    case PN_TRANSPORT_CLOSED:
        /* TODO aconway 2017-06-12: ignoring transport errors from dummy connections used ot 
           probe to see if we are listening. */
        /* fail_if_condition(e, pn_transport_condition(pn_event_transport(e))); */
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

    case PN_PROACTOR_INACTIVE:
        return false;

    default:
        break;
    }
    return true;
}

void run(struct arrow *a) {
    while(true) {
        pn_event_batch_t *events = pn_proactor_wait(a->proactor);
        for (pn_event_t *e = pn_event_batch_next(events); e; e = pn_event_batch_next(events)) {
            if (!handle(a, e)) {
                return;
            }
        }
        pn_proactor_done(a->proactor, events);
    }
}

bool find_flag(const char* want, const char* flags) {
    size_t len = strlen(want);
    const char* found = strstr(want, flags);
    /* Return true only if what we found is ',' delimited or at start/end of flags */
    return (found &&
            (found == flags || *(found-1) == ',') &&
            (*(found+len) == '\0' || *(found+len) == ','));
}

int token(const char *names[], const char *name) {
    size_t i = 0;
    for (; names[i] && strcmp(names[i], name); ++i)
        ;
    if (!names[i]) {
        FAIL("unknown token: %s", name);
    }
    return i;
}

int main(int argc, char** argv) {
    if (argc == 1) {
        printf("Qpid Proton C %d.%d.%d\n", PN_VERSION_MAJOR, PN_VERSION_MINOR, PN_VERSION_POINT);
        return 0;
    }

    int transaction_size = atoi(argv[11]);

    if (transaction_size > 0) {
        FAIL("this impl doesn't support transactions");
    }

    struct arrow a = { 0 };
    a.connection_mode = (connection_mode)token(connection_mode_names, (argv[1]));
    a.channel_mode = (channel_mode)token(channel_mode_names, (argv[2]));
    a.operation = (operation)token(operation_names, (argv[3]));
    a.id = argv[4];
    a.host = argv[5];
    a.port = argv[6];
    a.path = argv[7];
    a.messages = atoi(argv[8]);
    a.body_size = atoi(argv[9]);
    a.credit_window = atoi(argv[10]);
    const char *flags = argv[12];
    a.durable = find_flag("durable", flags);

    /* Set up the fixed parts of the message. */
    a.message = pn_message();
    pn_message_set_durable(a.message, a.durable);
    char *body = (char*)malloc(a.body_size);
    memset(body, 'x', a.body_size);
    pn_data_put_string(pn_message_body(a.message), pn_bytes(a.body_size, body));
    free(body);

    /* Connect or listen  */
    char addr[PN_MAX_ADDR];
    pn_proactor_addr(addr, sizeof(addr), a.host, a.port);
    a.proactor = pn_proactor();
    switch (a.connection_mode) {
    case CLIENT:
        a.connection = pn_connection();
        pn_proactor_connect(a.proactor, a.connection, addr);
        break;
    case SERVER:
        a.listener = pn_listener();
        pn_proactor_listen(a.proactor, a.listener, addr, 32);
        break;
    }

    run(&a);

    if (a.message) pn_message_free(a.message);
    if (a.proactor) pn_proactor_free(a.proactor);
    free(a.buffer.start);
    return 0;
}
