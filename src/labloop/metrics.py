"""Pulling a single number out of an experiment's output.

Two formats are supported, tried in this order:

1. A ``key=value`` or ``key: value`` pair anywhere in the output.
2. A JSON object on its own line containing ``key``.

The last occurrence within the first matching format wins. A later JSON line
does not override an earlier key/value pair; callers should use one format.

Experiments that stream a metric (``loss = ...`` every epoch) want that.
Experiments whose run prints the metric once can demand it: with
``strict=True`` a repeated key raises :class:`MetricAmbiguous` instead of
picking, because a repeat printed after the real value — by the very code
under measurement — is indistinguishable from an honest progress line.
"""

from __future__ import annotations

import json
import re

__all__ = ["extract_metric", "MetricNotFound", "MetricAmbiguous"]


class MetricNotFound(LookupError):
    """The named metric did not appear in the output."""


class MetricAmbiguous(MetricNotFound):
    """The key appeared more than once in the chosen format, under strict mode.

    Its own subclass of MetricNotFound so a caller that only catches
    MetricNotFound treats a repeat as "no usable metric" — while code that
    cares can name the reason. A repeat is refused, not resolved: the last
    line wins honestly when an experiment streams, but the last line also
    wins for an attacker who prints after the real value, and the loop
    cannot tell those apart. Failing the trial is the fail-closed reading.
    """


# nan and inf are matched because experiments print them: a diverged training
# run says `loss = nan`, and reporting that as "no metric" would send you to
# check your print statement instead of your learning rate. Deciding what such
# a value means is the loop's job, not the parser's. The trailing boundary
# keeps `status = info` from reading as infinity.
_NUMBER = (
    r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?"
    r"|[-+]?(?:nan|inf(?:inity)?)\b"
)


def extract_metric(output: str, key: str, *, strict: bool = False) -> float:
    """Return the last value of `key` in the first matching output format.

    Raises MetricNotFound if the key never appears, rather than returning a
    sentinel. A missing metric is a broken experiment, not a bad score, and
    the loop treats the two differently.

    With ``strict``, raise MetricAmbiguous instead of choosing when the key
    appears more than once in the format that matched. Off by default:
    streaming experiments legitimately repeat a metric, and last-wins is
    their contract.

    The result may be nan or inf. Those are values the experiment printed, so
    reporting them is honest; refusing to compare them is the loop's job.
    """
    value = _from_key_value(output, key, strict=strict)
    if value is not None:
        return value

    value = _from_json_lines(output, key, strict=strict)
    if value is not None:
        return value

    raise MetricNotFound(f"metric {key!r} not found in output")


def _word_edge(char: str) -> str:
    r"""A `\b` only where one can match.

    `\b` sits between a word character and a non-word one, so appending it to
    a key ending in `)` or `%` demands a word character that is never there —
    `loss(train) = 1.5` would not be found, though the JSON form finds it. The
    boundary still guards keys that end in a word character, which is where it
    earns its keep: `val_loss` must not match `total_val_loss_scaled`.
    """
    return r"\b" if char.isalnum() or char == "_" else ""


def _from_key_value(output: str, key: str, *, strict: bool = False) -> float | None:
    pattern = re.compile(
        rf"{_word_edge(key[:1])}{re.escape(key)}{_word_edge(key[-1:])}"
        rf"\s*[=:]\s*({_NUMBER})",
        re.IGNORECASE,
    )
    matches = [float(found) for found in pattern.findall(output)]
    if not matches:
        return None
    if strict and len(matches) > 1:
        raise MetricAmbiguous(
            f"metric {key!r} printed {len(matches)} times; strict mode refuses "
            "to pick between repeats — a line printed after the real value "
            "could be forging it"
        )
    return matches[-1]


def _from_json_lines(output: str, key: str, *, strict: bool = False) -> float | None:
    found: list[float] = []
    for line in output.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and key in obj:
            try:
                found.append(float(obj[key]))
            except (TypeError, ValueError):
                continue
    if not found:
        return None
    if strict and len(found) > 1:
        raise MetricAmbiguous(
            f"metric {key!r} in {len(found)} JSON lines; strict mode refuses "
            "to pick between repeats"
        )
    return found[-1]
