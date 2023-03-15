from datetime import timedelta


def ftime(time: int, add_ms: bool = True) -> str:
    '''
    Turns ms time into a formatted time string
    '''
    time = timedelta(milliseconds=time)

    minutes = str(time.seconds // 60).rjust(2, '0')
    seconds = str(int(time.seconds % 60)).rjust(2, '0')
    if add_ms:
        seconds += '.' + str(time.microseconds)[:-3].ljust(3, '0')
    return f'{minutes}:{seconds}'


def strtoms(time: str) -> int:
    '''
    Turns a string into its corresponding millisecond timestamp
    '''
    if not time or time.isalpha():
        return None

    times = list(filter(lambda t: t, time.split(':')))
    kwargs = zip(('minutes', 'seconds'), times)
    delta = timedelta(**{
        key: float(val) for key, val in kwargs
    })
    return delta.seconds * 1e3 + delta.microseconds / 1e3
