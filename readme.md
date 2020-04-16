# Usage
bsdl-injector is a tool used to automatically add new bsdl files to urjtag's database. 
To add your new bsdl files, all you need to do is run "injector.py <src> <dst>" where src is a directory that contains your bsdl files, and dst should be your urjtag's main database folder which also defaults to "/usr/local/share/urjtag".

# bsdl integrity check
Each file in the <src> directory will then be tested using bsdl2jtag. If the file passes bsdl2jtag's test, it is considered a valid bsdl file and will be added to urjtag's database specified with <dst>. In case an invalid bsdl file is caught by bsdl2jtag, a subprocess.CalledProcessError exception will be caught. injector.py will print the bsdl file's path to notify the user which file(s) didn't pass the test and therefore won't be added to the database.

# bsdl attributes
injector.py will use the following methods to extract the respective bsdl attributes:
            -Bsdl._extract_idcode()              -Bsdl.idcode
            -Bsdl._extract_part_name()         -Bsdl.part_name
            -Bsdl._extract_manufacturer_name()   -Bsdl.manufacturer_name

# adding manufacturers (JEDEC's JEP106)
If a manufacturer is already a urjtag manufacturer, it will not be added, but its correct name will be extracted from urjtag's MANUFACTRERS file.
If the the manufacturer specified in a bsdl file isn't already a urjtag manufacturer, its name will be taken from JEDEC's table ("./manufacturers" file) and added to urjtag.

# adding parts
If a part is already found in urjtag's database, it will not be added but its correct part_name will be extracted from the correct PARTS file.
If the new urjtag part isn't already a urjtag part, its part_name will be the bsdl's entity_name.

# one bsdl for many revisions
Often, bsdl files are used for various revisions of the same chip, this will affect how the revision (stepping) is specified in the bsdl file. eq: ("XX10", "0X1X", "XXXX", "1100").
Since we know Urjtag needs a specific revision number and can't make due with the pattern mentioned above, injector.py will generate all 4-bit binary combinations which fit the pattern specified in your bsdl, and add all of them as steppings for the new part.


Dependencies:
    bsdl2jtag (is installed by installing urjtag)
