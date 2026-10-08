# ProHand SDK

This repository hosts the ProHand SDK and driver, with the ProGlove and
ProWristCam SDKs that go with the hand. There is one product line per branch.
`main` carries no code: pick the line that matches your hardware and clone
that branch.

| Product line | Branch | Firmware | SDK / driver | Status |
|---|---|---|---|---|
| ProHand Gen1 (Gen1.A, Gen1.D) | `release/gen1` | 0.9.x | SDK 0.3.17.0 | maintenance |
| ProHand Gen2 Power | `release/gen2` | 1.3.0 and later | SDK 0.4.13.0, driver 0.4.14 | current |

The lines are not interchangeable. A Gen2 driver does not connect to Gen1
firmware, and a Gen1 driver does not connect to Gen2 firmware. Use the branch
for the hand you have.

## Get a line

```bash
git clone --branch release/gen2 --single-branch https://github.com/Proception-AI/prohand-sdk.git
# or
git clone --branch release/gen1 --single-branch https://github.com/Proception-AI/prohand-sdk.git
```

Already cloned? `git fetch origin && git checkout release/gen2`.

## Releases

Every release is a tag named `<line>/<sdk-version>`:

```bash
git tag -l 'gen2/*'            # releases of the Gen2 Power line
git checkout gen2/0.4.13.0     # pin to one
```

Each branch has its own README, INDEX.md and CHANGELOG.md for that line.

## Support

- Issues: https://github.com/Proception-AI/prohand-sdk/issues
- Email: contact@proception.ai
- Security: [SECURITY.md](SECURITY.md) · Contributing: [CONTRIBUTING.md](CONTRIBUTING.md) · [LICENSE](LICENSE)
