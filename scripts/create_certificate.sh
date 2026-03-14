#!/bin/bash
#
# Creates a self-signed code signing certificate for Not Wispr Flow
#
# IMPORTANT: Uses /usr/bin/openssl (macOS LibreSSL) explicitly.
# Homebrew's OpenSSL 3.x produces PKCS12 files that macOS keychain can't import.
#

set -e

CERT_NAME="Not Wispr Flow Dev"

# Remove ALL existing certificates AND their private keys
while security delete-identity -c "$CERT_NAME" ~/Library/Keychains/login.keychain-db 2>/dev/null; do :; done

cat > /tmp/cert_config.conf <<CONF
[ req ]
default_bits = 2048
distinguished_name = req_distinguished_name
x509_extensions = codesign_ext
[ req_distinguished_name ]
commonName = $CERT_NAME
[ codesign_ext ]
basicConstraints = critical,CA:FALSE
keyUsage = critical,digitalSignature
extendedKeyUsage = codeSigning
CONF

/usr/bin/openssl req -new -newkey rsa:2048 -x509 -days 3650 -nodes \
  -out /tmp/cert.pem -keyout /tmp/key.pem \
  -config /tmp/cert_config.conf -subj "/CN=$CERT_NAME"

/usr/bin/openssl pkcs12 -export -out /tmp/cert.p12 \
  -inkey /tmp/key.pem -in /tmp/cert.pem -passout pass:notwisprflow

security import /tmp/cert.p12 -k ~/Library/Keychains/login.keychain-db \
  -T /usr/bin/codesign -T /usr/bin/security -P "notwisprflow"

# Trust the self-signed cert for code signing
security add-trusted-cert -d -r trustRoot -p codeSign \
  -k ~/Library/Keychains/login.keychain-db /tmp/cert.pem

# Set partition list so codesign can access the key without a password prompt (macOS 10.12+)
# This requires the login keychain password (your macOS login password) — one-time only
echo ""
read -s -p "Enter your macOS login password (to allow passwordless code signing): " KC_PASS
echo ""
security set-key-partition-list -S apple-tool:,apple:,codesign: \
  -s -k "$KC_PASS" ~/Library/Keychains/login.keychain-db > /dev/null
unset KC_PASS

rm -f /tmp/cert.pem /tmp/key.pem /tmp/cert.p12 /tmp/cert_config.conf

echo ""
echo "Certificate '$CERT_NAME' created and trusted for code signing!"
