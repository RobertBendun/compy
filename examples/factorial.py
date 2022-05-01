def factorial(n) -> int:
    return 1 if n < 2 else n * factorial(n-1)

def test_factorial(n):
    print(n, "! = ", factorial(5), sep="")

test_factorial(5)
