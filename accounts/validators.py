import re
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _


class NumberValidator:
    """Password must contain at least one number."""

    def validate(self, password, user=None):
        if not re.search(r'\d', password):
            raise ValidationError(
                _("Password must contain at least one number."),
                code='password_no_number',
            )
        
    def get_help_text(self):
        return _("Your password must contain at least one number.")


class UppercaseValidator:
    """Password must contain at least one uppercase letter."""

    def validate(self, password, user=None):
        if not re.search(r'[A-Z]', password):
            raise ValidationError(
                _("Password must contain at least one uppercase letter."),
                code='password_no_upper',
            )
        
    def get_help_text(self):
        return _("Your password must contain at least one uppercase letter.")


class LowercaseValidator:
        """Password must contain at least one lowercase letter."""

        def validate(self, password, user=None):
            if not re.search(r'[a-z]', password):
                raise ValidationError(
                    ("Password must contain at least one lowercase letter."),
                    code='passowrd_no_lower',
                )
            
        def get_help_text(self):
            return _("Your password must contain at least one lowercase letter.")
        

class SpecialCharacterValidator:
    """Password must contain at least one special character."""

    SPECIAL_CHARACTERS = r'[!@#$%^&*(),.?":{}|<>_\-+=\[\]\\;\'`~/]'

    def validate(self, password, user=None):
        if not re.search(self.SPECIAL_CHARACTERS, password):
            raise ValidationError(
                _("Password must contain at least one special character "
                  "(!@#$%^&*...)."),
                code='password_no_special',
            )

    def get_help_text(self):
        return _(
            "Your password must contain at least one special character."
        )


class NoWhitespaceValidator:
    """Password must not contain spaces."""

    def validate(self, password, user=None):
        if re.search(r'\s', password):
            raise ValidationError(
                _("Password must not contain spaces."),
                code='password_has_whitespace',
            )

    def get_help_text(self):
        return _("Your password must not contain spaces.")
