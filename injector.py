import re
import os
import subprocess
import sys

class Bsdl():
    def __init__(self, path: str, dst: str):
        try:
            # path definitions
            self.path = path
            self.dst = dst
            self.urjtag_manufacturers_f = f"{self.dst}/MANUFACTURERS"
            self.jedec_manufacturers_path = "./manufacturers"

            # check bsdl integrity
            self._is_valid()    

            # initialize bsdl attributes
            self.idcode = ''
            self.part_name = ''     
            self.manufacturer_name = ''

            with open(self.path, 'r') as bsdl_fd:
                self.content = bsdl_fd.read()
            self._extract_idcode()

            self._extract_manufacturer_name()
            self.manufacturer_path = f"{self.dst}/{self.manufacturer_name}/"
            self.urjtag_parts_f = f"{self.manufacturer_path}/PARTS"

            self._extract_part_name()
            self.part_path = f"{self.manufacturer_path}/{self.part_name}/"
            self.urjtag_steppings_f = f"{self.part_path}/STEPPINGS"
            
        except subprocess.CalledProcessError:
            print(f"invalid bsdl file ({self.path})\n")

    def _extract_idcode(self):
        """extract idcode from bsdl file""" 
        idcode_re = re.compile("attribute IDCODE_REGISTER .* \"1\";", re.DOTALL)
        self.idcode = re.search(idcode_re, self.content)[0].split("\n")
        self.version_number, self.part_number, self.manufacturer_id = [field.split('\"')[1] for field in self.idcode[1:4]]
        self.idcode = self.version_number + self.part_number + self.manufacturer_id
    
    def _extract_part_name(self):
        """extract entity's name from bsdl file"""
        # extract part name used in urjtag's database if it already exists
        if self._is_urjtag_part():
            with open(self.urjtag_parts_f, 'r') as urjtag_parts_fd:
                urjtag_parts = urjtag_parts_fd.readlines()
            for part in urjtag_parts:
                if self.part_number in part:
                    self.part_name = part.split('\t')[1].lower()

        # extract part_name from bsdl's entity name 
        else:
            entity_declaration = re.search("entity .* is", self.content)
            self.part_name = entity_declaration[0].split()[1].lower()
    
    def _extract_manufacturer_name(self):
        """extract manufacturer name from urjtag's database or JEP106"""
        # extract manufacturer name used in urjtag's database if it already exists
        if self._is_urjtag_manufacturer():
            with open(self.urjtag_manufacturers_f, 'r') as urjtag_manufacturers_fd:
               urjtag_manufacturers = urjtag_manufacturers_fd.readlines() 
            for manufacturer in urjtag_manufacturers:
                if self.manufacturer_id in manufacturer:
                    self.manufacturer_name = manufacturer.split('\t')[1].lower()

        # extract manufacturer name from jedec's jep106, in case urjtag's database doesn't have it
        else:
            with open(self.jedec_manufacturers_path ,'r') as jedec_manufacturers_fd:
                jedec_manufacturers = jedec_manufacturers_fd.readlines()
            for manufacturer in jedec_manufacturers:
                if self.manufacturer_id in manufacturer:
                    self.manufacturer_name = manufacturer.strip().split()[-1].lower()

    def _is_valid(self) -> bool:
        """raise subprocess.CalledProcessError if bsdl file is invalid"""
        subprocess.run(["bsdl2jtag", self.path, "/dev/null"], check=True)

    def _copy(self):
        """copy bsdl file to urjtag's database"""
        subprocess.run(["cp", self.path, f"{self.part_path}/{self.part_name}"], check=True)    

    def _add_urjtag_manufacturer(self):
        """update urjtag's MANUFACTURERS ddf. create manufacturer folder and PARTS file."""
        # update MANUFACTURERS ddf
        with open(self.urjtag_manufacturers_f, 'a') as urjtag_manufacturers_fd:
            urjtag_manufacturers_fd.write(f"{self.manufacturer_id}\t{self.manufacturer_name}\t{self.manufacturer_name.capitalize()}\n")    

        # create manufacturer folder and PARTS file
        os.mkdir(self.manufacturer_path)
        with open(self.urjtag_parts_f, 'w') as urjtag_parts_fd:
           urjtag_parts_fd.write("# PARTS file created by bsdl-injector.py\n")

    def _add_urjtag_part(self):
        """update urjtag's PARTS ddf. create part folder and STEPPINGS file."""
        # update PARTS ddf
        with open(self.urjtag_parts_f, 'a') as urjtag_parts_fd:
            urjtag_parts_fd.write(f"{self.part_number}\t{self.part_name}\t{self.part_name.upper()}\n")

        # create part folder and STEPPINGS file
        os.mkdir(self.part_path)
        with open(self.urjtag_steppings_f, 'a') as urjtag_steppings_fd:
            urjtag_steppings_fd.write("# STEPPINGS file created by bsdl-injector.py\n")    
    
    def _add_urjtag_stepping(self, stepping: str):
        """add stepping to urjtag's stepping ddf"""
        with open(self.urjtag_steppings_f, 'a') as steppings_fd: 
            steppings_fd.write(f"{stepping}\t{self.part_name}\t{stepping}\n")

    def _is_urjtag_manufacturer(self) -> bool:
        """returns True if manufacturer_id exists in urjtag's database, otherwise returns False"""
        with open(self.urjtag_manufacturers_f, 'r') as urjtag_manufacturers_fd:
            urjtag_manufacturers = urjtag_manufacturers_fd.read()
        return True if self.manufacturer_id in urjtag_manufacturers else False 
    
    def _is_urjtag_part(self) -> bool:
        """returns True if part exists in urjtag's database, otherwise returns False"""
        with open(self.urjtag_parts_f, 'r') as urjtag_parts_fd:
            urjtag_parts = urjtag_parts_fd.read()
        return True if self.part_name in urjtag_parts else False

    def _is_urjtag_stepping(self, stepping: str) -> bool:
        """returns True if part's stepping exists in urjtag's database, otherwise returns False"""
        with open(self.urjtag_steppings_f, 'r') as urjtag_steppings_fd:
            urjtag_steppings = urjtag_steppings_fd.read()
        return True if stepping in urjtag_steppings else False

    def _generate_steppings(self) -> list:
        """return a list of steppings that match bsdl's version_number pattern"""
        steppings = []
        # if version_number is digits only, no need for pattern matching.
        if self.version_number.isdigit():
            steppings.append(self.version_number)

        else:
            combination_count = 2 ** len(self.version_number)
            steppings_re = re.compile(re.sub(r"[^0-1]", "[0-1]{1}", self.version_number))   # compile regex to detect anything that's not '0' or '1' in version_number
            for stepping in range(0, combination_count):
                stepping = f"{stepping:04b}" # convert int to binary representing str eq: 1 --> 0001
                if re.match(steppings_re, stepping): 
                    steppings.append(stepping)
        return steppings

    def add_to_urjtag(self):
        """add bsdl to urjtag database. creates the necessary files and folders to do so"""
        # add manufacturer if needed
        if not self._is_urjtag_manufacturer():
            self._add_urjtag_manufacturer()
        # add part if needed
        if not self._is_urjtag_part():
            self._add_urjtag_part()
        # add all steppings that match bsdl pattern eq:"XX11"
        steppings = [stepping for stepping in self._generate_steppings() if not self._is_urjtag_stepping(stepping)]
        for stepping in steppings:
            self._add_urjtag_stepping(stepping)
        # copy bsdl to urjtag's database only if there are new steppings to add.
        # if no new steppings are found, the bsdl_file is probably already in urjtag's database.
        if steppings != []:
            self._copy()
            print(f"{self.path}, added successfully\n")

if __name__ == '__main__':
    try:
        src = sys.argv[1] # directory which contains bsdl files
        dst = "/usr/local/share/urjtag/" # default urjtag database path
        if len(sys.argv > 3): # destination folder, urjtag's database 
            dst = sys.argv[2] 
        
        bsdl_files = [src + bsdl_file for bsdl_file in os.listdir(src)] # create list of absolute paths to each file in src directory
        # add all bsdl file in src to urjtag's database
        for bsdl_file in bsdl_files:
            bsdl = Bsdl(bsdl_file, dst)
            bsdl.add_to_urjtag()

    except (IndexError, FileNotFoundError):
        print("Usage: python3 injector.py <src> <dst>\n")
