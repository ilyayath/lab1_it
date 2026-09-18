"""Типи полів таблиці.

Кожен тип уміє розібрати текст із форми (parse), перетворити значення на
JSON і назад (to_json / from_json), показати його користувачеві (format)
і звести до канонічного вигляду для порівняння рядків (normalize).
"""

import math
from abc import ABC, abstractmethod

from .complex_values import ComplexInteger, ComplexReal, format_real
from .errors import ValidationError

# Точність порівняння дійсних значень: 9 знаків після коми.
DIGITS = 9


def is_number(data):
    """Число з JSON (bool у Python теж int, тому відкидається окремо)."""
    return isinstance(data, (int, float)) and not isinstance(data, bool)


def real_from_json(data):
    if is_number(data):
        try:
            value = float(data)
        except OverflowError:
            value = math.inf
        if math.isfinite(value):
            return value
    raise ValidationError(f"«{data}» не є скінченним дійсним числом")


def int_from_json(data):
    if not isinstance(data, int) or isinstance(data, bool):
        raise ValidationError(f"«{data}» не є цілим числом")
    return data


def complex_parts(data):
    if not isinstance(data, dict) or "re" not in data or "im" not in data:
        raise ValidationError(f"«{data}» не є комплексним числом виду {{\"re\": …, \"im\": …}}")
    return data["re"], data["im"]


class DataType(ABC):
    """Абстрактний тип поля таблиці."""

    name = ""
    # Підказка про формат, яку GUI показує поруч із полем введення.
    hint = ""

    @abstractmethod
    def parse(self, raw):
        """Перетворює текст на значення типу або кидає ValidationError."""

    def to_json(self, value):
        return value

    def from_json(self, data):
        return data

    def format(self, value):
        return "" if value is None else str(value)

    def normalize(self, value):
        return value


class IntegerType(DataType):
    name = "integer"
    hint = "ціле число, напр. -42"

    def parse(self, raw):
        text = raw.strip()
        if not text:
            raise ValidationError("Порожнє значення; очікується ціле число")
        try:
            return int(text)
        except ValueError:
            raise ValidationError(f"«{raw}» не є цілим числом")

    def from_json(self, data):
        return int_from_json(data)


class RealType(DataType):
    name = "real"
    hint = "дійсне число, напр. -3.14"

    def parse(self, raw):
        text = raw.strip().replace(",", ".")
        if not text:
            raise ValidationError("Порожнє значення; очікується дійсне число")
        try:
            value = float(text)
        except ValueError:
            raise ValidationError(f"«{raw}» не є дійсним числом")
        if not math.isfinite(value):
            raise ValidationError(f"«{raw}» не є скінченним числом")
        return value

    def from_json(self, data):
        return real_from_json(data)

    def format(self, value):
        return "" if value is None else format_real(value)

    def normalize(self, value):
        # Округлення до 9 знаків після коми, щоб близькі значення збігалися.
        return round(value, DIGITS)


class CharType(DataType):
    name = "char"
    hint = "рівно один символ, напр. A"

    def parse(self, raw):
        if len(raw) != 1:
            raise ValidationError(
                f"«{raw}» має довжину {len(raw)}; тип char вимагає рівно один символ"
            )
        return raw

    def from_json(self, data):
        if not isinstance(data, str):
            raise ValidationError(f"«{data}» не є символом")
        return self.parse(data)


class StringType(DataType):
    name = "string"
    hint = "довільний рядок"

    def parse(self, raw):
        return raw

    def from_json(self, data):
        if not isinstance(data, str):
            raise ValidationError(f"«{data}» не є рядком")
        return data


class ComplexIntegerType(DataType):
    name = "complexInteger"
    hint = "комплексне ціле, напр. 3+4i"

    def parse(self, raw):
        return ComplexInteger.parse(raw)

    def to_json(self, value):
        return {"re": value.re, "im": value.im}

    def from_json(self, data):
        re_part, im_part = complex_parts(data)
        return ComplexInteger(int_from_json(re_part), int_from_json(im_part))


class ComplexRealType(DataType):
    name = "complexReal"
    hint = "комплексне дійсне, напр. 3.5-0.25i"

    def parse(self, raw):
        return ComplexReal.parse(raw)

    def to_json(self, value):
        return {"re": value.re, "im": value.im}

    def from_json(self, data):
        re_part, im_part = complex_parts(data)
        return ComplexReal(real_from_json(re_part), real_from_json(im_part))

    def normalize(self, value):
        return round(value.re, DIGITS), round(value.im, DIGITS)
