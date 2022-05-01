def preallocate():
    nums : any = [0] * 10

    for i in range(len(nums)):
        nums[i] = i

    print(nums)

def append():
    nums : list = []
    for i in range(10):
        nums.append(i)
    print(nums)

preallocate()
append()
