def factorial(n) -> int:
    i : int = i
    result : int = 1
    while i <= n:
        result *= i
        i += 1
    return result


print("5! = ", factorial(5), sep="")
