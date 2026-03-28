"""Testes para validação de senha."""

from auth import validate_password


class TestPasswordValidation:
    def test_valid_password(self):
        assert validate_password("Str0ng!Pass") is None

    def test_too_short(self):
        assert validate_password("Ab1!") is not None

    def test_no_uppercase(self):
        assert validate_password("abcdefg1!") is not None

    def test_no_lowercase(self):
        assert validate_password("ABCDEFG1!") is not None

    def test_no_digit(self):
        assert validate_password("Abcdefg!!") is not None

    def test_no_special(self):
        assert validate_password("Abcdefg12") is not None
