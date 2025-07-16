# coding: utf-8
import json

import requests

from ..classes import Sheet
from .base import InterfaceBase


class DataInterface(InterfaceBase[Sheet]):

    FIELDS = [
        'sheets.properties(sheetId,title,gridProperties)',
        'sheets.data.rowData.values(formattedValue,hyperlink,note)',
        'sheets.data.rowData.values.effectiveFormat.textFormat.strikethrough',
        'sheets.data.rowData.values.textFormatRuns(startIndex,format(link,strikethrough))',
    ]

    def __init__(self, api_key: str | None, spreadsheet_id: str, sheet_ids: list[int]):
        super(DataInterface, self).__init__()

        if not api_key:
            raise self.MissingAPIKey(f'Google API key is required.')

        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Backlog Exporter (gzip)',
            'Accept-Encoding': 'gzip',
            'X-Goog-Api-Key': api_key,
        })
        url = f'https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}'

        print(msg := 'fetching spreadsheet via API...', end='\r')
        resp = session.get(
            url=url,
            headers={'X-Goog-FieldMask': 'sheets.properties(sheetId,title)'},
            params={'prettyPrint': False},
        )
        data = self.handle_response(resp)

        ranges = [
            f"'{props['title']}'" for sheet in data['sheets']
            if (props := sheet['properties']) and props['sheetId'] in sheet_ids
        ]

        print(f'fetching {len(ranges)} sheets via API...'.ljust(len(msg)))
        resp = session.get(
            url=url,
            headers={'X-Goog-FieldMask': ','.join(self.FIELDS)},
            params={'prettyPrint': False, 'ranges': ranges},
        )
        data = self.handle_response(resp)

        for sheet in data['sheets']:
            try:
                obj = Sheet.parse(sheet)
            except Exception as error:
                sheet_index = data['sheets'].index(sheet)
                raise Exception(f'Failed to parse sheet #{sheet_index}') from error

            if obj.id not in sheet_ids:
                continue

            try:
                obj.parse_data(sheet)
            except Exception as error:
                raise Exception(f'Failed to parse sheet "{obj.title}" ({obj.id})') from error

            self._sheets[obj.id] = obj

    @staticmethod
    def handle_response(resp: requests.Response) -> dict:
        try:
            data = resp.json()
        except ValueError:
            data = {}

        if error := data.get('error'):
            for key in ('code', 'status', 'message',):
                print(f'{key}={error.pop(key, None)}')
            if details := error.pop('details', []):
                print(f'details={json.dumps(details, indent=2)}')
            if error:
                print(error)

        if not resp.ok:
            details = '.' if data else f': {resp.text}'
            raise Exception('Request failed' + details)
        return data


    class MissingAPIKey(Exception):
        ...

