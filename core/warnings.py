def warning(percent):
    if percent < 76:
        return "CRITICAL"
    elif percent < 80:
        return "WARNING"
    else:
        return "SAFE"
