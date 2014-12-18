# PEP 263
# -*- coding: utf8 -*-
# version 0.0.3
__author__ = 'Aleksei Gusev'


import urllib2
from math import exp
from math import pow
from math import sqrt
from urllib import urlencode
from datetime import datetime
from HTMLParser import HTMLParser


class _rp5Parser(HTMLParser):
    weather_data = {'untag': ()}
    __subkey = None
    __tag_name = None
    __class_archiveinfo = 0

    def handle_starttag(self, tag, attrs):
        if tag == 'div':
            __attrs = dict(attrs)
            if __attrs.get('class', '').lower() == 'archiveinfo':
                self.__tag_name = tag
                self.__class_archiveinfo = 1

        if self.__class_archiveinfo and tag == 'span':
            __attrs = dict(attrs)
            if __attrs.get('class'):
                self.__subkey = __attrs['class']

    def handle_endtag(self, tag):
        if tag == 'div' and self.__class_archiveinfo:
            self.__class_archiveinfo = 0

        if tag == 'span' and self.__subkey:
            self.__subkey = None

    def handle_data(self, data):
        data = data.strip()
        if self.__class_archiveinfo and data:
            data = data.strip(r',()')
            if self.__subkey:
                self.weather_data[self.__subkey] = data
            else:
                self.weather_data['untag'] += (data,)

    def get_url(self, url):
        try:
            response = urllib2.urlopen(url)
        except Exception as e:
            self.weather_data['error'] = e.args
            return self.weather_data

        if response.code != 200:
            self.weather_data['error'] = ('HTTP %s' % response.code,)
            return self.weather_data

        self.feed(response.read())

        return self.weather_data


class rp5ForecastParser(HTMLParser):
    year = datetime.now().year
    weather_data = {}
    _archTableRowLimit = 0
    __forecasttable = 0
    __tr = 0
    __td = 0
    __tkey = ''
    __tr_num = 0
    __td_num = 0
    __tag_class = ''

    def handle_starttag(self, tag, attrs):

        if tag == 'table' and dict(attrs).get('id') == 'forecastTable':
            self.__forecasttable = 1

        if tag == 'tr' and self.__forecasttable:
            self.__tr = 1
            self.__tr_num += 1

        if tag == 'td' and self.__forecasttable and self.__tr:
            self.__td = 1
            self.__td_num += 1

            if self.__td_num > 2:
                self.__tr = 0
                # print('--'*80)

        if self.__forecasttable and self.__tr and self.__td:
            __attrs = dict(attrs)
            if __attrs.get('class'):
                if 'title' in __attrs['class']:
                    self.__tag_class = 'title'
                else:
                    self.__tag_class = (__attrs.get('class', '').replace('underTitle', '')
                                        .replace('underlineRow', '').strip().replace(' ', '_'))

    def handle_endtag(self, tag):
        if tag == 'table' and self.__forecasttable:
            self.__forecasttable = 0

        if tag == 'tr' and self.__forecasttable:
            self.__tr = 0
            self.__td_num = 0

        if tag == 'td' and self.__forecasttable and self.__tr:
            self.__td = 0

    def handle_data(self, data):
        data = data.strip()
        # data = data.strip('(,)')

        if self.__forecasttable and self.__tr and self.__td and data:
            # print(self.__tag_class, self.__tr_num, self.__td_num, data)
            # print(self.__tag_class, data)
            if self.__tag_class == 'title':
                self.weather_data[data] = {}
                self.__tkey = data
                # print('__tkey', data)
            else:
                if self.__tkey:
                    if self.weather_data[self.__tkey].get(self.__tag_class):
                        self.weather_data[self.__tkey][self.__tag_class].insert(0, data)
                    else:
                        self.weather_data[self.__tkey][self.__tag_class] = [data]
                    # print(self.__tkey, self.__tag_class, data)

    def get_weather(self, url):
        try:
            response = urllib2.urlopen(url)
        except Exception as e:
            self.weather_data['error'] = e.args
            return self.weather_data

        if response.code != 200:
            self.weather_data['error'] = ('HTTP %s' % response.code,)
            return self.weather_data

        self.feed(response.read())

        return self.weather_data


class rp5ArchiveParser(HTMLParser):
    data = []
    year = None
    row_l = []
    keys_l = []
    c_data_d = {}
    month_day = []
    encoding = 'utf8'
    weather_data_l = []
    _tzOffset = 0
    _archTableRowLimit = 0
    __tr = 0
    __td = 0
    __tr_num = 0
    __td_num = 0
    __tag = ''
    __tag_class = ''
    __archivetable = 0
    __rowspan = 0

    def _float(self, data):
        if data:
            if isinstance(data, dict):
                data_d = {}
                try:
                    for k, v in data.items():
                        data_d[k] = float(v)
                    return data_d
                except ValueError as e:
                    print(e)
                    return data

        return data

    def _Humidex(self, t):
        # Humidex http://en.wikipedia.org/wiki/Humidex
        humidex_e = 6.11 * exp(5417.7530 * ((1 / 273.16) - (1 / (273.15 + t))))
        return t + 0.5555 * (humidex_e - 10.0)

    def _Tse_C_ms(self, t, v):
        # Simple Effective temperature
        # t -2 * v
        return t - 2 * v

    def _Twc_C_kmh(self, t, v):
        # # en wiki wind chill canadian, C and km/h http://en.wikipedia.org/wiki/Wind_chill
        # wind chill original:
        # print(10 * sqrt(data_d['Ff']['wv_0'] - data_d['Ff']['wv_0'] + 10.5) * (33 - data_d['T']['t_0']))
        if t > 10.0:
            return t
        return 13.12 + 0.6215 * t - 11.37 * pow(v, 0.16) + 0.3965 * t * pow(v, 0.16)

    def _Twc_F_mph(self, t, v):
        # # en wiki wind chill canadian, F and mph http://en.wikipedia.org/wiki/Wind_chill
        if t > 50.0:
            return t
        return 35.74 + 0.6215 * t - 35.75 * pow(v, 0.16) + 0.4275 * t * pow(v, 0.16)

    def _cloud_cover(self, data_l):
        data_d = {}
        if isinstance(data_l, (tuple, list)):
            data_str = ''.join(data_l)
            data_str = data_str.decode(self.encoding)
            data_str = data_str.replace(unichr(8211), '-')
            data_split = data_str.split('.')
            if len(data_split) == 3:
                n0_l = data_split[0].replace('%', '').replace(' ', '').strip().split('-')

                try:
                    data_d['cc_0'] = (float(n0_l[0]) + float(n0_l[-1])) / 2
                    data_d['cc_1'] = data_d['cc_0'] / 100
                except Exception as e:
                    print(e)

                if data_split[2][:3].isdigit():
                    data_d['cc_2'] = float(data_split[2][:3])
                elif data_split[2][:2].isdigit():
                    data_d['cc_2'] = float(data_split[2][:2])
                elif data_split[2][:1].isdigit():
                    data_d['cc_2'] = float(data_split[2][:1])

        return data_d

    def _date_convert(self, data):
        dt = datetime.now()
        pdt = dt
        if len(data) == 4:
            try:
                pdt = datetime.strptime('%s %s %02d %s' % (data[0], data[1], int(data[2]), data[3]), '%Y %B %d %A')
                self.year = pdt.year
            except Exception as e:
                print(e)
        elif len(data) == 3:
            try:
                pdt = datetime.strptime('%s %02d %s' % (data[0], int(data[1]), data[2]), '%B %d %A')
                if self.year:
                    pdt = pdt.replace(year=self.year)
                else:
                    pdt = pdt.replace(year=dt.year)
            except Exception as e:
                print(e)

        return datetime(year=pdt.year, month=pdt.month, day=pdt.day).strftime('%Y-%m-%d')

    def clean(self):
        for data_d in self.weather_data_l:
            if data_d.get('Ff'):
                data_d['_Ff'] = data_d['Ff'].copy()
                try:
                    for k, v in data_d['Ff'].items():
                        if k.startswith('wv_'):
                            data_d['Ff'][k] = float(v.split(' ')[0])
                        elif k == 'cl':
                            data_d['Ff']['cl_nt'] = data_d['Ff'].pop('cl', None)
                        else:
                            data_d['Ff'][k] = v
                except ValueError as e:
                    print(k, v, e)
                    data_d['Ff'] = data_d['_Ff']
            else:
                data_d['Ff'] = {'cl': 'Calm, no wind', 'wv_0': '0', 'wv_1': '0', 'wv_2': '0', 'wv_3': '0', 'wv_4': '0'}

            if data_d.get('N'):
                # data_d['__N'] = data_d['N']
                data_d['N'] = self._cloud_cover(data_d['N'])

            if data_d.get('Nh'):
                # data_d['__Nh'] = data_d['Nh']
                data_d['Nh'] = self._cloud_cover(data_d['Nh'])

            if data_d.get('T'):
                data_d['T'] = self._float(data_d['T'])

            if data_d.get('Tn'):
                data_d['Tn'] = self._float(data_d['Tn'])

            if data_d.get('Tx'):
                data_d['Tx'] = self._float(data_d['Tx'])

            if data_d.get('Td'):
                data_d['Td'] = self._float(data_d['Td'])

            if data_d.get('VV'):
                for k, v in data_d['VV'].items():
                    data_d['VV'][k] = v.split(' ')[0]
                data_d['VV'] = self._float(data_d['VV'])

            if data_d.get('P'):
                data_d['P'] = self._float(data_d['P'])

            if data_d.get('Pa'):
                data_d['Pa'] = self._float(data_d['Pa'])

            if data_d.get('Po'):
                data_d['Po'] = self._float(data_d['Po'])

            if data_d.get('RRR'):
                data_d['RRR'] = self._float(data_d['RRR'])

    def phys_n_math(self):
        for data_d in self.weather_data_l:
            if data_d.get('Ff', {}).get('wv_0') is not None and data_d.get('T', {}).get('t_0') is not None:
                data_d['Tse'] = {'t_0': self._Tse_C_ms(data_d['T']['t_0'], data_d['Ff']['wv_0'])}

            data_d['Twc'] = {}
            if data_d.get('T', {}).get('t_0') is not None and data_d.get('Ff', {}).get('wv_1') is not None:
                data_d['Twc']['t_0'] = self._Twc_C_kmh(data_d['T']['t_0'], data_d['Ff']['wv_1'])

            if data_d.get('T', {}).get('t_1') is not None and data_d.get('Ff', {}).get('wv_2') is not None:
                data_d['Twc']['t_1'] = self._Twc_F_mph(data_d['T']['t_1'], data_d['Ff']['wv_2'])

            if data_d.get('T', {}).get('t_0') is not None:
                data_d['Humidex'] = self._Humidex(data_d['T']['t_0'])

    def handle_starttag(self, tag, attrs):

        if tag == 'table':
            if dict(attrs).get('id', '').lower() == 'archivetable':
                self.__archivetable = 1

        if tag == 'tr' and self.__archivetable:
            self.__tr = 1
            self.__tr_num += 1
            self.__td_num = 0
            # # handle only first data row:
            if self._archTableRowLimit:
                if self.__tr_num > (self._archTableRowLimit + 1):
                    self.__archivetable = 0

        if tag == 'td' and self.__archivetable and self.__tr:
            self.__td = 1
            self.__td_num += 1
            if dict(attrs).get('rowspan'):
                self.__rowspan = 0

        if tag in ['div', 'span', 'br'] and self.__archivetable and self.__tr and self.__td:
            __attrs = dict(attrs)
            self.__tag_class = __attrs.get('class', '').replace('dfs', '').strip().replace(' ', '_')

    def handle_endtag(self, tag):
        if tag == 'table' and self.__archivetable:
            self.__archivetable = 0

        if tag == 'td' and self.__archivetable and self.__tr:
            self.__td = 0
            self.__tag_class = ''
            if self.__tr_num == 1:
                self.keys_l.append(':'.join(self.c_data_d.values()))
                self.c_data_d = {}
            else:
                if self.c_data_d:
                    if len(self.c_data_d) > 1:
                        self.data.append(self.c_data_d.copy())
                    else:
                        self.data.append(self.c_data_d.values()[0])
                    self.c_data_d = {}
                else:
                    self.data.append('')

        if tag == 'tr' and self.__archivetable:
            self.__tag_class = ''
            if self.__tr_num == 1:
                self.keys_l = self.data
            else:
                if self.__rowspan > 0:
                    self.data.insert(0, self.month_day)
                else:
                    # self.month_day = self.data[0] = self._date_convert(self.data[0]['_noic_'], self.data[0]['cl_dt'])
                    self.month_day = self.data[0] = self._date_convert(self.data[0])
                    # self.month_day = self.data[0]
                    # self._date_convert(self.data[0])

                self.row_l.append(self.data)
                # datetime_key = '%s %s:00:00' % (self.data[0], self.data[1])
                # self.weather_data[datetime_key] = dict(zip(self.keys_l[2:], self.data[2:]))
                self.weather_data_l.append(dict(zip(self.keys_l, self.data)))

            # print(len(self.data), self.__tr_num, self.__rowspan, self.data) ; print('--'*80)
            self.__rowspan += 1
            self.__tr = 0
            self.c_data_d = {}
            self.data = []

    def handle_data(self, data):
        data = data.strip()
        data = data.strip('(,)')

        if self.__archivetable and self.__tr and self.__td and data:
            if '/ local time' in str(data).lower():
                data = 'Localtime'

            if self.__tr_num == 1:
                self.data.append(data)
            else:
                # print('2 ##> %s' % (self.__tag_class))
                __key = '%s' % (self.__tag_class or '_noic_')
                if self.c_data_d.get(__key):
                    # # self.c_data_d[__key].append(data)
                    if self.c_data_d[__key]:
                        if isinstance(self.c_data_d[__key], list):
                            self.c_data_d[__key].append(data)
                        else:
                            self.c_data_d[__key] = [self.c_data_d[__key], data]
                    else:
                        self.c_data_d[__key] = data
                else:
                    # # self.c_data_d[__key] = [data]
                    self.c_data_d[__key] = data

    def get_weather(self, url, date=datetime.now(), lang='ru', tzoffset=3, archTableRowLimit=None, encoding=None):
        if isinstance(date, datetime):
            date = date.strftime('%d.%m.%Y')

        self.encoding = encoding or 'utf8'

        if archTableRowLimit:
            if isinstance(archTableRowLimit, (int, float)):
                self._archTableRowLimit = int(archTableRowLimit)

        # 3  3.5  -3  -3.5  '0300'  '1040'  '-300'  '-1030'
        if tzoffset:
            if isinstance(tzoffset, (int, float)):
                self._tzOffset = float(tzoffset)
            if isinstance(tzoffset, (str, tuple(u''))):
                if tzoffset.isdigit():
                    self._tzOffset = float(tzoffset)
                else:
                    self._tzOffset = 3

        try:
            data = {'ArchDate': date, 'time_zone_add': str(tzoffset),
                    'pe': '1', 'lang': str(lang)}
            response = urllib2.urlopen(url, urlencode(data))
        except Exception as e:
            self.weather_data_l.append({'error': e.args})
            return self.weather_data_l

        if response.code != 200:
            self.weather_data_l.append({'error': 'HTTP %s' % response.code})
            return self.weather_data_l

        html = response.read()
        # # with open('p_dump.html', 'wb') as p:
        # #     p.write(html)

        self.feed(html)
        self.clean()

        return self.weather_data_l


if __name__ == '__main__':

    """
    T   - Air temperature at 2 metre height above the earth`s surface
          t_0 - degrees Celsius; t_1 - degrees Fahrenheit
    Tse - Simple effective(effective) air temperature
    Tn  - Minimum air temperature during the past period (not exceeding 12 hours)
    Tx  - Maximum air temperature during the past period (not exceeding 12 hours)
    Td  - Dewpoint temperature at a height of 2 metres above the earth's surface
    U   - Relative humidity (%) at a height of 2 metres above the earth's surface
    N/c - Total cloud cover
          cc_0 - %; cc_1 - relative; cc_2 - oktas
    Nh  - Amount of all the CL cloud present or, if no CL cloud is present, the amount of all the CM cloud present
    Ff  - Mean wind speed at a height of 10-12 metres above the earth’s surface
          over the 10-minute period immediately preceding the observation
          wv_0 - m/s; wv_1 - km/h; wv_2 - mph; wv_3 - knots; wv_4 - Bft
    WW  - Present weather reported from a weather station
    W1  - Past weather (weather between the periods of observation) 1
    W2  - Past weather (weather between the periods of observation) 2
    Cl  - Clouds of the genera Stratocumulus, Stratus, Cumulus and Cumulonimbus
    H   - Height of the base of the lowest clouds (m)
    VV  - Horizontal visibility
          vv_0 - km; vv_1 - miles
    RRR - Amount of precipitation
          pr_0 - millimeters; pr_1 - inches
    Tr  - The period of time during which the specified amount of precipitation was accumulated
    """
    from pprint import pprint


    # Moscow weather:
    url_arch = 'http://rp5.ru/Weather_archive_in_Moscow'
    url_arch = 'http://rp5.ru/Weather_archive_in_Vnukovo_(airport)'
    url_arch = 'http://rp5.ru/Weather_archive_in_Vnukovo_(airport),_METAR'

    date = datetime.now()
    parser = rp5ArchiveParser()
    result = parser.get_weather(url_arch, date=date)
    parser.phys_n_math()
    pprint(result[0])


    # Moscow weather:
    url = 'http://rp5.ru/Weather_in_Vnukovo_(airport)'

    parser = rp5ForecastParser()
    result = parser.get_weather(url)
    pprint(result)


