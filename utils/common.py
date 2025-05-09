from typing import *

T = TypeVar('T')
U = TypeVar('U')


def full_outer_join(
        first: Iterable[T],
        second: Iterable[U],
        eq: Callable[[T, U], bool]
) -> List[Tuple[Optional[T], Optional[U]]]:
    result = []
    second = list(second)
    second_matches = {j: False for j in second}
    for i in first:
        first_matched = False
        for j in second:
            if eq(i, j):
                first_matched = True
                second_matches[j] = True
                result.append((i, j))
        if not first_matched:
            result.append((i, None))
    result.extend((None, k) for k, v in second_matches.items() if not v)
    return result

