def chunks(l, n):
    """Yield successive n-sized chunks from l."""
    return list(l[i : i + n] for i in range(0, len(l), n))
