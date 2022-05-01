def factorial_while(n) -> int:
    i : int = i
    result : int = 1
    while i <= n:
        result *= i
        i += 1
    return result

def factorial_for(n) -> int:
    result : int = 1
    for i in range(1, n+1):
        result *= i
    return result


print("5! = ", factorial_while(5), sep="")
print("5! = ", factorial_for(5), sep="")
