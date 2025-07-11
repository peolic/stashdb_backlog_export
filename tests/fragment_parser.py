#!/usr/bin/env python3

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Union

here = Path(__file__).parent.resolve()
sys.path[1:1] = [str(here.parent)]

from extract.classes import SheetCell
from extract.sheets.performers_to_split_up import PerformersToSplitUp


class SheetExtractor(PerformersToSplitUp):
    def __init__(self):
        pass

@dataclass
class Expected:
    name: str
    text: Optional[str] = None
    notes: Optional[List[str]] = None
    labels: int = 0

@dataclass
class Example:
    text: str
    note: str = ''
    expected: Optional[Expected] = None

Examples = List[Union[str, Example]]

def run_parser_test(examples: Examples):
    parser = SheetExtractor()
    for i, example in enumerate(examples, 1):
        if isinstance(example, Example):
            raw = example.text
            fragment_cell = SheetCell(example.text, [], example.note, False)
        else:
            raw = example
            fragment_cell = SheetCell(example, [], '', False)

        result = parser._parse_fragment_cell(fragment_cell, '')
        if not result:
            print('no result for:', raw)
            break
        labels = [*SheetExtractor.LABELS_PATTERN.finditer(raw)]
        print(f"{i:<4} raw: {result['raw']!r}")
        print(f"name: {result['name']!r}")
        print(f"text: {result.get('text')!r}")
        print(f"notes: {result.get('notes')!r}")
        print(f"labels: {', '.join(repr((m.group(), *m.span())) for m in labels)}")

        if expected := (isinstance(example, Example) and example.expected) or None:
            test_ok = True
            if expected.name != (result_name := result['name']):
                print('!!!', f'Expected `name`: {expected.name!r}', '|', f'Got: {result_name!r}')
                test_ok = False
            if expected.text != (result_text := result.get('text', None)):
                print('!!!', f'Expected `text`: {expected.text!r}', '|', f'Got: {result_text!r}')
                test_ok = False
            if expected.notes != (result_notes := result.get('notes', None)):
                print('!!!', f'Expected `notes`: {expected.notes!r}', '|', f'Got: {result_notes!r}')
                test_ok = False
            if expected.labels != (label_count := len(labels)):
                print('!!!', f'Expected labels: {expected.labels}', '|', f'Got: {label_count}')
                test_ok = False
            print('!!!', f'links: {result.get("links")}')

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
        text='Nadine (Nubiles)\n[ixxx] [nude]\n- Nubiles',
        expected=Expected(
            name='Nadine (Nubiles)',
            labels=2,
            text='Nubiles',
        ),
    ),
    Example(
        text='Mimi (2007, Reality Kings) [iafd] [ixxx]\n- MILF Hunter (2007)',
        note='Possible AKA: Mimi Rio',
        expected=Expected(
            name='Mimi (2007, Reality Kings)',
            labels=2,
            text='MILF Hunter (2007)',
            notes=['Possible AKA: Mimi Rio'],
        ),
    ),
    Example(
        text='Henessy\n[iafd] [ixxx]\n- Teen Mega World',
        note='additional scenes missing performers\n\u0002https://deleted-link-to-scene\u0003\nhttps://link-to-scene',
        expected=Expected(
            name='Henessy',
            labels=2,
            text='Teen Mega World',
            notes=[
                'additional scenes missing performers',
            ],
        ),
    ),
    Example(
        text='Lena Love [iafd] [ixxx]\n- Dirty Flix (should be Yana?)',
        note='- \u000218videoz\u0003\n- \u0002Kink\u0003\n- \u0002Teen Mega World\u0003',
        expected=Expected(
            name='Lena Love',
            labels=2,
            text=None,
            notes=[
                '- Dirty Flix (should be Yana?)',
                '- \u000218videoz\u0003',
                '- \u0002Kink\u0003',
                '- \u0002Teen Mega World\u0003',
            ],
        ),
    ),
    Example(
        text='Tiana [iafd]\nAKA Tiana Ross\nAKA Tiana Barbel\nAKA Tiana Ason\n- 21sextury',
        expected=Expected(
            name='Tiana',
            labels=1,
            text='AKA Tiana Ross',
            notes=[
                'AKA Tiana Barbel',
                'AKA Tiana Ason',
                '- 21sextury',
            ],
        ),
    ),
    Example(
        text='Eva Gomez AKA Eva F, Eva M. \n[iafd] [ixxx] \nDevil\'s TGirls',
        expected=Expected(
            name='Eva Gomez AKA Eva F, Eva M.',
            labels=2,
            text='Devil\'s TGirls',
        ),
    ),
    Example(
        text='Tamara N\'Joy [ixxx] [stash1] [stash2]',
        expected=Expected(
            name='Tamara N\'Joy',
            labels=3,
        ),
    ),
    Example(
        text='[iafd] [ixxx]',
        expected=Expected(
            name='[no name provided]',
            labels=2,
        ),
    ),
    Example(
        text='[iafd] [ixxx] (2008, Street BlowJobs)',
        expected=Expected(
            name='[no name provided]',
            labels=2,
            text='(2008, Street BlowJobs)',
        ),
    ),
    Example(
        text='Lara Page [iafd] [ixxx] (ddf)',
        expected=Expected(
            name='Lara Page',
            labels=2,
            text='(ddf)',
        ),
    ),
    Example(
        text='Mika (Nasty Angels) \npossibly the linked [iafd] profile, unconfirmed',
        expected=Expected(
            name='Mika (Nasty Angels)',
            labels=1,
            text='possibly the linked profile, unconfirmed',
        ),
    ),
    Example(
        text='Rimma [iafd] [ixxx]\n\u0002- 21sextury\u0003',
        expected=Expected(
            name='Rimma',
            labels=2,
            text='\u000221sextury\u0003',
        ),
    ),
    Example(
        text='Jay Dee \n[iafd]\n(\u0002at least all sexyhub.com, \u0003possibly ddf)',
        expected=Expected(
            name='Jay Dee',
            labels=1,
            text='(\u0002at least all sexyhub.com, \u0003possibly ddf)',
        ),
    ),
    Example(
        text='Inga Zolva [ixxx]\n- should be done ?\n- \u0002Nubiles\u0003',
        expected=Expected(
            name='Inga Zolva',
            labels=1,
            notes=[
                '- should be done ?',
                '- \u0002Nubiles\u0003',
            ],
        ),
    ),
    Example(
        text='Ginger B. - [iafd] [ixxx] \n- probably most scenes',
        expected=Expected(
            name='Ginger B.',
            labels=2,
            text='probably most scenes',
        ),
    ),
    Example(
        text='Zenza Raggi \n[iafd] \n(18 Flesh scene - Naughty Newbies - Scene 2, and more 18 Flesh scenes)\n(unlisted alias)',
        expected=Expected(
            name='Zenza Raggi',
            labels=1,
            text='(18 Flesh scene - Naughty Newbies - Scene 2, and more 18 Flesh scenes)',
            notes=['(unlisted alias)'],
        ),
    ),
    Example(
        text='Tanya (RU) or Kissme J [iafd] [ixxx]\n- Spoiled Virgins (2004)',
        expected=Expected(
            name='Tanya (RU) or Kissme J',
            labels=2,
            text='Spoiled Virgins (2004)',
        ),
    ),
    Example(
        text='Stephanna (RU) AKA Princess Kathrin \n[iafd] [ixxx]\n- Old-n-Young\n- Gap-n-Gape',
        expected=Expected(
            name='Stephanna (RU) AKA Princess Kathrin',
            labels=2,
            notes=['- Old-n-Young', '- Gap-n-Gape'],
        ),
    ),
    Example(
        text='Mocha (RU) \n[iafd] [ixxx]\n- Lez Cuties\n- Cuties Galore\n- Beauty Angels\n- more ?',
        expected=Expected(
            name='Mocha (RU)',
            labels=2,
            notes=[
                '- Lez Cuties',
                '- Cuties Galore',
                '- Beauty Angels',
                '- more ?',
            ],
        ),
    ),
]

# text = (here / 'raw_fragments.txt').read_text()
# examples = [e.replace('\\n', '\n') for e in text.splitlines()]
# examples = [e for i, e in enumerate(text.splitlines(), 1) if '- ' in e and i >= 34]
# import random; examples = random.choices([e for i, e in enumerate(text.splitlines(), 1) if ('- ' in e and '\\n' in e) and i >= 34], k=100)

if __name__ == '__main__':
    run_parser_test(examples)
