#!/bin/bash
#
# Removes the Not Wispr Flow code signing certificate from the keychain
#

CERT_NAME="Not Wispr Flow Dev"

if ! security find-certificate -c "$CERT_NAME" ~/Library/Keychains/login.keychain-db > /dev/null 2>&1; then
    echo "Certificate '$CERT_NAME' not found in keychain."
    exit 0
fi

echo "Removing certificate '$CERT_NAME'..."
while security delete-identity -c "$CERT_NAME" ~/Library/Keychains/login.keychain-db 2>/dev/null; do :; done
echo "Done."
