"""A tiny sample POC: reverse a string. Stands in for whatever you built."""


def reverse(text: str) -> str:
    return text[::-1]


if __name__ == "__main__":
    import sys
    print(reverse(" ".join(sys.argv[1:]) or "hello"))
