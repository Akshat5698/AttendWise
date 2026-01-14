def future_percent(attended,total):
    return (attended/(total+1))*100

def bunk_allowed(attended,total):
    return future_percent(attended,total) >= 75

def can_bunk(attended, total):
    future = (attended / (total + 1)) * 100
    return future >= 75, round(future, 2)
