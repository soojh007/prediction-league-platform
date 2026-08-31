# Contributing to Prediction League Platform

Thank you for your interest in contributing! We welcome bug fixes, feature enhancements, and documentation improvements.

---

## 🛠️ Development Setup

1. **Fork and Clone the Repository**:
   ```bash
   git clone https://github.com/<your-username>/prediction-league-platform.git
   cd prediction-league-platform
   ```

2. **Set Up Python Environment**:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Initialize Database & Seed Demo Data**:
   ```bash
   python manage.py migrate
   python manage.py seed_demo
   ```

4. **Run the Test Suite**:
   ```bash
   python manage.py test
   ```

---

## 📋 Submitting Changes

1. Create a feature branch:
   ```bash
   git checkout -b feature/my-new-feature
   ```
2. Write clean, documented code and ensure all tests pass.
3. Commit your changes with descriptive commit messages:
   ```bash
   git commit -m "feat(leagues): add tie-breaker rule for goal difference"
   ```
4. Push to your branch and open a Pull Request against `main`.
