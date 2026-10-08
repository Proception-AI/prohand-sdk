# Security Policy

## Reporting Security Vulnerabilities

Proception Inc. takes the security of our SDK and hardware systems seriously. If you discover a security vulnerability, please report it responsibly.

### How to Report

**DO NOT** open a public GitHub issue for security vulnerabilities.

Instead, please report security issues to:

- **Email**: contact@proception.ai
- **Subject**: [Security] Brief description of the issue

### What to Include

Please provide as much information as possible:

- Type of vulnerability (e.g., authentication bypass, injection, DoS)
- Affected SDK version(s)
- Platform and hardware model
- Steps to reproduce the issue
- Potential impact
- Proof-of-concept (if applicable)
- Suggested fix (if you have one)

### Response Timeline

- **Acknowledgment**: Within 48 hours
- **Initial Assessment**: Within 5 business days
- **Status Updates**: Every 7 days until resolved
- **Fix Release**: Varies by severity (critical issues prioritized)

### Disclosure Policy

- We will work with you to understand and address the issue
- We ask that you do not publicly disclose the issue until we have released a fix
- We will credit you in the security advisory (unless you prefer to remain anonymous)
- We may request a CVE number for significant vulnerabilities

### Scope

**In Scope:**

- SDK libraries and binaries
- IPC communication protocols
- Authentication and authorization
- Data validation and input handling
- Cryptographic implementations
- Firmware update mechanisms

**Out of Scope:**

- Physical attacks on hardware
- Denial of Service via hardware abuse
- Issues in third-party dependencies (report to maintainers)
- Social engineering attacks

### Security Best Practices

When using the Proception SDK:

1. **Keep SDK Updated**: Use the latest version for security patches
1. **Network Security**:
   - Use firewalls to restrict ZeroMQ endpoint access
   - Do not expose IPC ports to untrusted networks
1. **Firmware Updates**: Only install official firmware from proception.ai
1. **Access Control**: Restrict physical and software access to hardware
1. **Input Validation**: Validate all commands and sensor data in your application
1. **Logging**: Monitor logs for suspicious activity

### Contact

- **General Support**: contact@proception.ai
- **Sales Team**: sales@proception.ai
- **Website**: https://proception.ai

______________________________________________________________________

**Proception Inc.**
Updated: 2026-09-22
