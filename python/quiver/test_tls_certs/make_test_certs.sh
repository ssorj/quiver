#!/usr/bin/env bash
# Creates the TLS certificates used by the tests.

make_pn_cert()
{
  name=$1
  subject=$2
  passwd=$3
  openssl req -newkey rsa:2048 -keyout ${name}-private-key.pem -out ${name}-certificate.pem -subj ${subject} -passout pass:${passwd} -x509 -days 3650
  openssl rsa -in ${name}-private-key.pem -out ${name}-private-key-nopwd.pem -passin pass:${passwd}
}

make_pn_cert tserver /CN=test_server/OU=quiver_test password
make_pn_cert tclient /CN=test_client/OU=quiver_test password
