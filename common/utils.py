def convert_to_pk(fn):
	def wrapper(*args, **kwargs):
		newargs = []
		for arg in args:
			if isinstance(arg, int):
				newargs.append(arg)
			elif hasattr(arg, "pk"):
				newargs.append(arg.pk)
			else:
				raise TypeError(repr(arg) + " is not convertible to int")
		return fn(*newargs, **kwargs)

	return wrapper
