def convert_to_pk(fn):
	def wrapper(*args, **kwargs):
		newargs = []
		for arg in args:
			if isinstance(arg, int):
				newargs.append(arg)
			else:
				newargs.append(arg.pk)
		return fn(*newargs, **kwargs)
	return wrapper
