# PEP 263
# -*- coding: utf8 -*-
# version 0.0.1
__author__ = 'Aleksei Gusev'

# Moscow south weather:
url = 'http://rp5.ru/%D0%9F%D0%BE%D0%B3%D0%BE%D0%B4%D0%B0_' \
      '%D0%B2_%D0%9C%D0%BE%D1%81%D0%BA%D0%B2%D0%B5_%28%D1%8E%D0%B3%29'


import urllib2
from HTMLParser import HTMLParser


class rp5Parser(HTMLParser):
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


if __name__ == '__main__':
    parser = rp5Parser()
    result = parser.get_url(url)

    # from pprint import pprint
    # pprint(result)

    for k, v in result.items():
        if isinstance(v, tuple):
            print('"%s" "%s"' % (k, ' '.join(v)))
        else:
            print('"%s" "%s"' % (k, v))