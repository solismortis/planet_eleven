def gfg_decorator(x):
    print('asd')


@gfg_decorator
def hello_decorator():
    print("Gfg")

'''Above code is equivalent to - 
  
def hello_decorator(): 
    print("Gfg") 
      
hello_decorator = gfg_decorator(hello_decorator)'''