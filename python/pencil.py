#
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
#

import os as _os
import re as _re
import time as _time

from pprint import pformat as _pformat

try:
    from urllib.parse import quote_plus as _url_escape
except ImportError:
    from urllib import quote_plus as _url_escape

try:
    from urllib.parse import unquote_plus as _url_unescape
except ImportError:
    from urllib import unquote_plus as _url_unescape

from xml.sax.saxutils import escape as _xml_escape
from xml.sax.saxutils import unescape as _xml_unescape

# String formatting functions

def nvl(value, substitution, template=None):
    assert substitution is not None

    if value is None:
        return substitution

    if template is not None:
        return template.format(value)

    return value

def shorten(s, max):
    if s is None:
        return ""

    assert max is not None
    assert isinstance(max, int)
    
    if len(s) < max:
        return s
    else:
        return s[0:max]

def init_cap(s):
    if s is None:
        return ""
    
    return s[0].upper() + s[1:]

def first_sentence(text):
    if text is None:
        return ""

    match = _re.search(r"(.+?)\.\s+", text, _re.DOTALL)

    if match is None:
        if text.endswith("."):
            text = text[:-1]
        
        return text
    
    return match.group(1)

def plural(noun, count=0):
    if noun is None:
        return ""

    if count == 1:
        return noun

    if noun.endswith("s"):
        return "{}ses".format(noun)

    return "{}s".format(noun)

def format_list(coll):
    if not coll:
        return

    return ", ".join([_pformat(x) for x in coll])

def format_dict(coll):
    if not coll:
        return

    if not isinstance(coll, dict) and hasattr(coll, "__iter__"):
        coll = dict(coll)

    out = list()
    key_len = max([len(str(x)) for x in coll])
    key_len = min(48, key_len)
    key_len += 2
    indent = " " * (key_len + 2)
    fmt = "%%-%ir  %%s" % key_len

    for key in sorted(coll):
        value = _pformat(coll[key])
        value = value.replace("\n", "\n{}".format(indent))
        args = key, value

        out.append(fmt % args)

    return _os.linesep.join(out)

def format_repr(obj, *args):
    cls = obj.__class__.__name__
    strings = [str(x) for x in args]
    return "{}({})".format(cls, ",".join(strings))

_date_format = "%Y-%m-%d %H:%M:%S"

def format_local_unixtime(utime=None):
    if utime is None:
        return

    return _time.strftime(_date_format + " %Z", _time.localtime(utime))

def format_local_unixtime_medium(utime):
    if utime is None:
        return

    return _time.strftime("%d %b %H:%M", _time.localtime(utime))

def format_local_unixtime_brief(utime):
    if utime is None:
        return

    now = _time.time()

    if utime > now - 86400:
        fmt = "%H:%M"
    else:
        fmt = "%d %b"

    return _time.strftime(fmt, _time.localtime(utime))

def format_datetime(dtime):
    if dtime is None:
        return

    return dtime.strftime(_date_format)

_duration_units = (
    (86400 * 365, 2, "year", "yr"),
    (86400 * 30,  2, "month", "mo"),
    (86400 * 7,   2, "week", "w"),
    (86400,       2, "day", "d"),
    (3600,        1, "hour", "h"),
    (60,          1, "minute", "m"),
)

def format_duration_coarse(seconds):
    for duration, threshold, name, abbrev in _duration_units:
        count = int(seconds / duration)

        if count >= threshold:
            return "{:2} {}".format(count, plural(name, count))

    return "{:2} {}".format(count, plural(name, count))

def format_duration_coarse_brief(seconds):
    for duration, threshold, name, abbrev in _duration_units:
        count = int(seconds / duration)

        if count >= threshold:
            return "{:2}{}".format(count, abbrev)

    return "{:2}{}".format(count, abbrev)

# String-related utilities

class StringCatalog(dict):
    def __init__(self, path):
        super().__init__()

        self.path = "{}.strings".format(_os.path.splitext(path)[0])

        with open(self.path) as file:
            strings = self._parse(file)

        self.update(strings)

    def _parse(self, file):
        strings = dict()
        key = None
        out = list()

        for line in file:
            line = line.rstrip()

            if line.startswith("[") and line.endswith("]"):
                if key:
                    strings[key] = "".join(out).strip()

                out = list()
                key = line[1:-1]

                continue

            out.append(line)

        strings[key] = _os.linesep.join(out).strip()

        return strings

    def __repr__(self):
        return format_repr(self, self.path)

# HTML functions

def url_escape(string):
    if string is None:
        return

    return _url_escape(string)

def url_unescape(string):
    if string is None:
        return

    return _url_unescape(string)

_extra_entities = {
    '"': "&quot;",
    "'": "&#x27;",
    "/": "&#x2F;",
}

def xml_escape(string):
    if string is None:
        return

    return _xml_escape(string, _extra_entities)

def xml_unescape(string):
    if string is None:
        return

    return _xml_unescape(string)

_strip_tags_regex = _re.compile(r"<[^<]+?>")

def strip_tags(string):
    if string is None:
        return

    return _re.sub(_strip_tags_regex, "", string)

def _html_elem(tag, content, attrs):
    attrs = _html_attrs(attrs)

    if content is None:
        content = ""
    
    return "<{}{}>{}</{}>".format(tag, attrs, content, tag)

def _html_attrs(attrs):
    vars = list()

    for name, value in attrs.items():
        if value is False:
            continue

        if value is True:
            value = name
            
        if name == "class_" or name == "_class":
            name = "class"

        vars.append(" {}=\"{}\"".format(name, xml_escape(value)))

    return "".join(vars)

def html_open(tag, **attrs):
    """<tag attribute="value">"""
    args = tag, _html_attrs(attrs)
    return "<{}{}>".format(tag, _html_attrs(attrs))

def html_close(tag):
    """</tag>"""
    return "</{}>".format(tag)

def html_elem(tag, content, **attrs):
    """<tag attribute="value">content</tag>"""
    return _html_elem(tag, content, attrs)

def html_p(content, **attrs):
    return _html_elem("p", content, attrs)

def html_tr(content, **attrs):
    return _html_elem("tr", content, attrs)

def html_th(content, **attrs):
    return _html_elem("th", content, attrs)

def html_td(content, **attrs):
    return _html_elem("td", content, attrs)

def html_li(content, **attrs):
    return _html_elem("li", content, attrs)

def html_a(content, href, **attrs):
    attrs["href"] = href

    return _html_elem("a", content, attrs)

def nvl_html_a(value, substitution, href_template):
    if value is None:
        return substitution

    return html_a(value, href_template.format(value))

def html_h(content, **attrs):
    return _html_elem("h1", content, attrs)

def html_div(content, **attrs):
    return _html_elem("div", content, attrs)

def html_span(content, **attrs):
    return _html_elem("span", content, attrs)

def html_section(content, **attrs):
    return _html_elem("section", content, attrs)

def html_table(items, first_row_headings=True, first_col_headings=False,
               escape_cell_data=False, **attrs):
    row_headings = list()
    rows = list()

    if first_row_headings:
        for cell in items[0]:
            row_headings.append(html_th(cell))

        rows.append(html_tr("".join(row_headings)))

        items = items[1:]
        
    for item in items:
        cols = list()

        for i, cell in enumerate(item):
            if escape_cell_data:
                cell = xml_escape(cell)
            
            if i == 0 and first_col_headings:
                cols.append(html_th(cell))
            else:
                cols.append(html_td(cell))

        rows.append(html_tr("".join(cols)))

    tbody = html_elem("tbody", "\n{}\n".format("\n".join(rows)))
        
    return _html_elem("table", tbody, attrs)

def html_ul(items, **attrs):
    out = list()
    
    for item in items:
        out.append(html_li(item))

    return _html_elem("ul", "".join(out), attrs)
