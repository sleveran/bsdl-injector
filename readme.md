bsdl-injector is a tool used to automatically add bsdl files to fit in urjtag's database structure. 
to add bsdl files, all you need to do is run bsdl-injector and give it a directory to look for bsdl files in. 
any file that ends in .bsd or .bsdl will be added to urjtag's database. 
a new part name should be the name of the bsdl file. 
if the the manufacturer isn't already in urjtag's manufacturers, it should be taken from the JEDEC manufacturer table and added to urjtag.
the device's stepping should be numbered the lowest number that isn't taken for this device. 
of course, with each step bsdl-injector will make sure it doesn't add anything that already exists - may it be a manufacturer, a part, or a stepping.
