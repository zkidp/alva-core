def solve(xs):
    balance = 0
    for amount in xs:
        balance += amount
        if balance < 0:
            return True
    return False
