#!/usr/bin/env python3

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

here = Path(__file__).parent.resolve()
sys.path[1:1] = [str(here.parent)]

from extract.classes import SheetCell
from extract.logger import LoggerMixin
from extract.models import PerformerEntry
from extract.sheets.scene_performers import ScenePerformers


class SheetExtractor(ScenePerformers):
    def __init__(self):
        self.skip_done = False
        self.skip_no_id = False
        LoggerMixin.__init__(self, 'scene')

@dataclass
class Expected:
    name: str
    id: Optional[str]
    disambiguation: Optional[str]
    appearance: Optional[str]
    status: Optional[str]
    status_url: Optional[str]
    notes: Optional[list[str]]

    @classmethod
    def from_entry(cls: 'type[Expected]', entry: PerformerEntry):
        return cls(
            name=entry['name'],
            id=entry['id'],
            disambiguation=entry.get('disambiguation'),
            appearance=entry['appearance'],
            status=entry.get('status'),
            status_url=entry.get('status_url'),
            notes=entry.get('notes'),
        )

@dataclass
class Example:
    text: str
    note: str = ''
    links: list[str] =  field(default_factory=list)
    expected: Optional[Expected] = None

Examples = list[Example]

result_keys = list(PerformerEntry.__annotations__.keys())
result_keys.remove('id')
result_keys.insert(0, 'id')

def run_parser_test(examples: Examples):
    parser = SheetExtractor()
    for i, example in enumerate(examples, 1):
        raw = example.text
        fragment_cell = SheetCell(i, example.text, example.links, [], example.note, False)

        result, result_raw = parser._get_change_entry(fragment_cell, i, 'scene-uuid')
        if not result:
            print('no result for:', raw)
            break

        print(f"{i:<4} raw: {result_raw!r}")
        for key in result_keys:
            if key in result:
                print(f"{key}: {result[key]!r}")

        if expected := (isinstance(example, Example) and example.expected) or None:
            test_ok = True
            expected_result = Expected.from_entry(result)
            for attr in Expected.__annotations__.keys():
                expected_value = getattr(expected, attr)
                result_value = getattr(expected_result, attr)
                if expected_value != result_value:
                    print('!!!', f'Expected `{attr}`: {expected_value!r}', '|', f'Got: {result_value!r}')
                    test_ok = False

            if test_ok:
                print(f'✔ Tested --- [{i}/{len(examples)}] ---\n')
                continue
            else:
                print(f'✖ Failed', end=' ')
        else:
            print('⚠ Untested', end=' ')

        try:
            input(f'--- [{i}/{len(examples)}] ---\n')
            continue
        except KeyboardInterrupt:
            break


examples: Examples = [
    Example(
        text='Marlena Mason',
        links=['https://stashdb.org/performers/ded1973e-daae-45f3-aff1-2085fb567b63'],
        expected=Expected(
            id='ded1973e-daae-45f3-aff1-2085fb567b63',
            name='Marlena Mason',
            disambiguation=None,
            appearance=None,
            status=None,
            status_url=None,
            notes=None,
        ),
    ),
    Example(
        text='Marlena Mason (as Marlena)',
        links=['https://stashdb.org/performers/ded1973e-daae-45f3-aff1-2085fb567b63'],
        expected=Expected(
            id='ded1973e-daae-45f3-aff1-2085fb567b63',
            name='Marlena Mason',
            disambiguation=None,
            appearance='Marlena',
            status=None,
            status_url=None,
            notes=None,
        ),
    ),
    Example(
        text='Marlena [Mason] (as Marlena)',
        links=['https://stashdb.org/performers/ded1973e-daae-45f3-aff1-2085fb567b63'],
        expected=Expected(
            id='ded1973e-daae-45f3-aff1-2085fb567b63',
            name='Marlena',
            disambiguation='Mason',
            appearance='Marlena',
            status=None,
            status_url=None,
            notes=None,
        ),
    ),
    Example(
        text='Marlena (Mason)',
        links=['https://stashdb.org/performers/ded1973e-daae-45f3-aff1-2085fb567b63'],
        expected=Expected(
            id='ded1973e-daae-45f3-aff1-2085fb567b63',
            name='Marlena',
            disambiguation='Mason',
            appearance=None,
            status=None,
            status_url=None,
            notes=None,
        ),
    ),
    Example(
        text='Marlena (Mason) (as Marlena)',
        links=['https://stashdb.org/performers/ded1973e-daae-45f3-aff1-2085fb567b63'],
        expected=Expected(
            id='ded1973e-daae-45f3-aff1-2085fb567b63',
            name='Marlena',
            disambiguation='Mason',
            appearance='Marlena',
            status=None,
            status_url=None,
            notes=None,
        ),
    ),
    Example(
        text='[new] Marlena Mason (as Marlena)',
        links=['https://www.iafd.com/person.rme/perfid=marlena/gender=f/marlena.htm'],
        expected=Expected(
            id=None,
            name='Marlena Mason',
            disambiguation=None,
            appearance='Marlena',
            status='new',
            status_url='https://www.iafd.com/person.rme/perfid=marlena/gender=f/marlena.htm',
            notes=None,
        ),
    ),
]

# text = (here / 'raw_fragments.txt').read_text()
# examples = [e.replace('\\n', '\n') for e in text.splitlines()]
# examples = [e for i, e in enumerate(text.splitlines(), 1) if '- ' in e and i >= 34]
# import random; examples = random.choices([e for i, e in enumerate(text.splitlines(), 1) if ('- ' in e and '\\n' in e) and i >= 34], k=100)

if __name__ == '__main__':
    run_parser_test(examples)
