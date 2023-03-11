def ftime(time: int, add_ms: bool = True) -> str:
    '''
    Turns ms time into a formatted time string
    '''
    s = time * 1e-3
    ms = int((s - int(s)) * 1e3)
    min = int(s // 60)

    formatted = f'{str(min).rjust(2, "0")}:{str(int(s) % 60).rjust(2, "0")}'
    if add_ms:
        formatted += f'.{str(ms).rjust(3, "0")}'
    return formatted


def strtoms(time) -> int:
    '''
    Turns a string into its corresponding millisecond timestamp
    '''
    m, s, ms = 0, 0, 0
    if not time or time.isalpha():
        return None

    # validate time formatting
    time = time.split(':')
    if not time[0]:
        return None
    if len(time) < 2 or time[0].isalpha() or time[1].isalpha():
        return None
    m = int(time[0])

    s_ms = time[1].split('.')
    if not s_ms[0] or s_ms[0].isalpha():
        return None
    s = int(s_ms[0])
    if len(s_ms) > 1 and not s_ms[1].isalpha():
        ms = int(s_ms[1])

    return int(((m * 60) + s) * 1e3 + ms)
