# Security Policy

## Supported Versions

Only the latest release receives security fixes. Update to the newest version before reporting a problem.

| Version | Supported |
| ------ | ------ |
| Latest release | Yes |
| Older releases | No |

## Reporting a Vulnerability

Do not open a public issue for a security problem. Report it privately through GitHub instead:

1. Open the [Security tab](https://github.com/alexhass/syr_connect/security) of this repository.
2. Select **Report a vulnerability**.
3. Describe the problem, the affected version and the steps to reproduce it.

Leave passwords, session tokens and serial numbers out of the report. Mask them in logs and diagnostics before attaching them.

The report is only visible to the maintainer. It is answered as soon as possible. A confirmed problem is fixed in a new release, and the advisory is published afterwards.

## Scope

In scope are problems in the code of this integration, for example:

- Handling of the SYR Connect credentials and session tokens
- Data that diagnostics or logs reveal unintentionally
- Requests to the cloud or the local device API that can be abused

Out of scope are problems in the SYR Connect cloud, the SYR app or the device firmware. Report them to SYR directly. Problems in Home Assistant itself belong to the [Home Assistant security policy](https://www.home-assistant.io/security/).
