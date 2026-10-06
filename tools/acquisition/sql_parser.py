"""Split schema SQL on statement terminators outside quoted text or blocks."""

import re


def statements(sql):
    result, current = [], []
    single = double = line_comment = block_comment = False
    dollar_tag = None
    index = 0
    while index < len(sql):
        char = sql[index]
        pair = sql[index:index + 2]
        if line_comment:
            current.append(char)
            line_comment = char != "\n"
        elif block_comment:
            current.append(char)
            if pair == "*/":
                current.append("/")
                index += 1
                block_comment = False
        elif dollar_tag:
            if sql.startswith(dollar_tag, index):
                current.append(dollar_tag)
                index += len(dollar_tag) - 1
                dollar_tag = None
            else:
                current.append(char)
        elif single or double:
            current.append(char)
            if (single and char == "'" and pair != "''") or (double and char == '"' and pair != '""'):
                single = double = False
            elif pair in ("''", '""'):
                current.append(char)
                index += 1
        elif pair == "--":
            current.extend(pair)
            index += 1
            line_comment = True
        elif pair == "/*":
            current.extend(pair)
            index += 1
            block_comment = True
        elif char == "'":
            current.append(char)
            single = True
        elif char == '"':
            current.append(char)
            double = True
        elif char == "$":
            match = re.match(r"\$(?:[A-Za-z_][A-Za-z0-9_]*)?\$", sql[index:])
            if match:
                dollar_tag = match.group(0)
                current.append(dollar_tag)
                index += len(dollar_tag) - 1
            else:
                current.append(char)
        elif char == ";":
            statement = "".join(current).strip()
            if statement:
                result.append(statement)
            current.clear()
        else:
            current.append(char)
        index += 1
    statement = "".join(current).strip()
    if statement:
        result.append(statement)
    return result
