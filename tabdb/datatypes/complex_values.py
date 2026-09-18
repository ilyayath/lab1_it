"""Значення додаткових типів варіанту: complexInteger і complexReal.

Обидва класи незмінні (frozen dataclass), тому їх можна класти у множини —
це потрібно для порівняння рядків в операції перетину.
"""

import math
import re
from dataclasses import dataclass

from .errors import ValidationError

# Число без знака: ціле для complexInteger, дійсне для complexReal.
UINT = r"\d+"
UREAL = r"(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?"


def format_real(value):
    """Найкоротший запис дійсного числа, що точно читається назад.

    На відміну від формату «g» (6 значущих цифр) не втрачає точності під час
    редагування; «1.0» скорочується до «1».
    """
    text = repr(float(value))
    return text[:-2] if text.endswith(".0") else text


def build_patterns(number):
    """Три форми запису: повна (3+4i), лише уявна (5i, -i), лише дійсна (7)."""
    return (
        re.compile(rf"^([+-]?{number})([+-])({number})?[ij]$"),
        re.compile(rf"^([+-]?(?:{number})?)[ij]$"),
        re.compile(rf"^[+-]?{number}$"),
    )


INT_PATTERNS = build_patterns(UINT)
REAL_PATTERNS = build_patterns(UREAL)


def parse_parts(raw, patterns, example):
    """Розкладає рядок на текстові дійсну та уявну частини."""
    text = raw.replace(" ", "")
    full, imaginary, real = patterns

    match = full.match(text)
    if match:
        real_part, sign, imag_part = match.groups()
        return real_part, sign + (imag_part or "1")

    match = imaginary.match(text)
    if match:
        imag_part = match.group(1)
        if imag_part in ("", "+"):
            imag_part = "1"
        elif imag_part == "-":
            imag_part = "-1"
        return "0", imag_part

    if real.match(text):
        return text, "0"

    raise ValidationError(f"«{raw}» не є комплексним числом; очікується, напр. «{example}»")


@dataclass(frozen=True)
class ComplexInteger:
    """Комплексне число з цілими дійсною та уявною частинами."""

    re: int
    im: int

    @staticmethod
    def parse(s):
        real_part, imag_part = parse_parts(s, INT_PATTERNS, "3+4i")
        return ComplexInteger(int(real_part), int(imag_part))

    def __str__(self):
        sign = "-" if self.im < 0 else "+"
        return f"{self.re}{sign}{abs(self.im)}i"


@dataclass(frozen=True)
class ComplexReal:
    """Комплексне число з дійсними частинами."""

    re: float
    im: float

    @staticmethod
    def parse(s):
        real_part, imag_part = parse_parts(s, REAL_PATTERNS, "3.5-0.25i")
        value = ComplexReal(float(real_part), float(imag_part))
        if not (math.isfinite(value.re) and math.isfinite(value.im)):
            raise ValidationError(f"«{s}» містить надто велике число")
        return value

    def is_close(self, other, eps=1e-9):
        """Чи збігаються числа з точністю до eps."""
        return (
            math.isclose(self.re, other.re, rel_tol=0.0, abs_tol=eps)
            and math.isclose(self.im, other.im, rel_tol=0.0, abs_tol=eps)
        )

    def __str__(self):
        sign = "-" if self.im < 0 else "+"
        return f"{format_real(self.re)}{sign}{format_real(abs(self.im))}i"
