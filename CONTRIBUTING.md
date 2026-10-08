# Contributing to Proception SDK

Thank you for your interest in contributing to the Proception SDK! We welcome contributions, especially for examples, demos, and documentation.

## How to Contribute

### Reporting Bugs

If you find a bug, please report it via:

- **GitHub Issues**: https://github.com/Proception-AI/pro-sdk/issues
- **Email**: contact@proception.ai

**Please include:**

- SDK version (check `INDEX.md` or git tag)
- Platform and OS version (macOS/Linux, ARM64/x64)
- Hardware model (ProHand/ProGlove/ProWristCam)
- Steps to reproduce the issue
- Expected vs actual behavior
- Relevant logs or error messages

### Suggesting Features

We welcome feature suggestions! Please:

1. Check existing issues to avoid duplicates
1. Open a GitHub issue with `[Feature Request]` in the title
1. Describe the use case and expected behavior
1. Explain why this would be useful to other users

### Contributing Examples and Demos

We especially encourage contributions to the demo applications!

**Examples you can contribute:**

- New motion patterns or control strategies
- Integration examples (ROS, Python frameworks, etc.)
- Utility scripts for common tasks
- Documentation improvements

**Process:**

1. Fork the repository
1. Create a feature branch: `git checkout -b feature/your-demo-name`
1. Add your example to `sdk/demo/python/` or `sdk/demo/cpp/`
1. Follow existing code style and structure
1. Test your example with actual hardware
1. Update documentation (add README or comments)
1. Submit a pull request

**Demo guidelines:**

- Use MIT license (demos are MIT-licensed)
- Include clear comments explaining what the code does
- Add usage instructions in a comment block or README
- Keep dependencies minimal
- Test on at least one platform

### Code Style

**Python:**

- Follow PEP 8
- Use type hints where appropriate
- Add docstrings for functions/classes

**C++:**

- Follow existing style in demo code
- Use modern C++ features (C++17)
- Include comments for complex logic
- Add CMakeLists.txt if introducing new dependencies

### Documentation Contributions

Documentation is licensed under CC BY 4.0, allowing remixing with attribution.

**Areas for contribution:**

- Tutorials and how-to guides
- API documentation improvements
- Translation to other languages
- Troubleshooting tips
- Best practices and patterns

### Pull Request Process

1. **Fork and clone** the repository
1. **Create a branch** for your changes
1. **Make your changes** following our guidelines
1. **Test thoroughly** with actual hardware if possible
1. **Update documentation** as needed
1. **Commit with clear messages**: `Add cyclic motion demo for wrist control`
1. **Push to your fork**
1. **Open a Pull Request** with:
   - Clear description of changes
   - Reference to related issues
   - Testing performed
   - Screenshots/videos if applicable

### Review Process

- We review PRs as quickly as possible (typically within 1-2 weeks)
- We may request changes or clarifications
- Once approved, we'll merge and credit you
- Your contribution will be included in the next release

## Core SDK Contributions

The core SDK libraries (`prohand_sdk`, `proglove_sdk`, `prowrist_sdk`) are proprietary and maintained internally by Proception Inc. We do not accept external contributions to these components.

However, feedback and bug reports are always welcome!

## Questions?

If you have questions about contributing:

- Open a GitHub Discussion
- Email: contact@proception.ai
- Check the documentation: `sdk/docs/`

## Code of Conduct

- Be respectful and professional
- Focus on constructive feedback
- Help make the SDK better for everyone
- Follow hardware safety guidelines when testing

## License

By contributing examples/demos, you agree to license your contribution under the MIT License.

By contributing documentation, you agree to license your contribution under CC BY 4.0.

______________________________________________________________________

Thank you for contributing to the Proception SDK!

**Proception Inc.**
Website: https://proception.ai
Support: contact@proception.ai
