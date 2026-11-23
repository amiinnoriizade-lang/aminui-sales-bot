# Changelog

## 0.1.2
- Fix order registration when one or more panel inbounds return `settings.clients` as null or malformed data.
- Ignore empty/non-object client entries safely while checking username uniqueness across inbounds.
- Add regression test for null `clients` responses.


## 0.1.2 (OpenVPN feature set)
- Add OpenVPN account provisioning for the Sir-MmD/vpn-ui API.
- Let the administrator choose TCP or UDP per fixed plan or volume-based service.
- Download the selected inbound's `.ovpn` profile from the panel API at delivery time; never bundle server profiles or certificates in the source repository.
- Send the `.ovpn` document with the customer's username and password, and add a resend action in the customer's account menu.
- Support OpenVPN account renewal, disable and delete using the panel's password identity.
- Persist transport selection through plans, services, orders and accounts with automatic SQLite migrations.
- Keep generic inbound IDs unset in the public `.env.example`; administrators select inbounds from Telegram.
- Add mocked OpenVPN API/account/profile tests.
