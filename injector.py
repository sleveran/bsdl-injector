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
            self.manufacturer_path = f"{self.dst}/{self.manufacturer_name}"
            self.urjtag_parts_f = f"{self.manufacturer_path}/PARTS"

            self._extract_part_name()
            self.part_path = f"{self.manufacturer_path}/{self.part_name}"
            self.urjtag_steppings_f = f"{self.part_path}/STEPPINGS"
            
        except subprocess.CalledProcessError:
            print(f"invalid bsdl file ({self.path})\n")

    def _extract_idcode(self):
        """extract and define the entity's idcode""" 
        idcode_re = re.compile("attribute IDCODE_REGISTER .* \"1\";", re.DOTALL)
        self.idcode = re.search(idcode_re, self.content)[0].split("\n")
        self.version_number, self.part_number, self.manufacturer_id = [field.split('\"')[1] for field in self.idcode[1:4]]
        self.idcode = self.version_number.upper() + self.part_number + self.manufacturer_id
    
    def _extract_part_name(self):
        """extract and define the part's name"""
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
        """extract and define the manufacturer name"""
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

    def _add_urjtag_manufacturer(self):
        """add Bsdl.manufacturer_id to urjtag's manufacturer ddf, and creates the manufacturer's folder"""
        # update MANUFACTURERS ddf
        with open(self.urjtag_manufacturers_f, 'a') as urjtag_manufacturers_fd:
            urjtag_manufacturers_fd.write(f"{self.manufacturer_id}\t{self.manufacturer_name}\t{self.manufacturer_name.capitalize()}\n")    

        # create manufacturer folder and PARTS file
        os.mkdir(self.manufacturer_path)
        with open(self.urjtag_parts_f, 'w') as urjtag_parts_fd:
           urjtag_parts_fd.write("# PARTS file created by bsdl-injector.py\n")

    def _add_urjtag_part(self):
        """add Bsdl.part_name to urjtag's part ddf, and creates the part's folder"""
        # update PARTS ddf
        with open(self.urjtag_parts_f, 'a') as urjtag_parts_fd:
            urjtag_parts_fd.write(f"{self.part_number}\t{self.part_name}\t{self.part_name.upper()}\n")

        # create part folder and STEPPINGS file
        os.mkdir(self.part_path)
        with open(self.urjtag_steppings_f, 'a') as urjtag_steppings_fd:
            urjtag_steppings_fd.write("# STEPPINGS file created by bsdl-injector.py\n")    
    
    def _add_urjtag_stepping(self, stepping: str):
        """add part stepping to urjtag's stepping ddf"""
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

    def _is_valid(self) -> bool:
        """raise subprocess.CalledProcessError if bsdl file is invalid"""
        subprocess.run(["bsdl2jtag", self.path, "/dev/null"], check=True)

    def _copy(self):
        subprocess.run(["cp", self.path, f"{self.part_path}/{self.part_name}"], check=True)    

    def _generate_steppings(self) -> list:
        steppings = []
        if self.version_number.isdigit():
            steppings.append(self.version_number)

        else:
            combination_count = 2**len(self.version_number)
            steppings_re = re.compile(self.version_number.replace("X", "[0-1]{1}"))
            for stepping in range(0, combination_count):
                stepping = f"{stepping:04b}"
                if re.match(steppings_re, stepping):
                    steppings.append(stepping)
        return steppings

    def add_to_urjtag(self):
        """add bsdl to urjtag database"""
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
        # copy bsdl to urjtag's database
        self._copy()
        print(f"{self.path}, added successfully\n")

if __name__ == '__main__':
    try:
        src = sys.argv[1] # directory which contains bsdl files
        if len(sys.argv > 3): # destination folder, urjtag's database 
            dst = sys.argv[2] 
        else:
            dst = "/usr/local/share/urjtag" # default urjtag database path

        bsdl_files = [src + bsdl_file for bsdl_file in os.listdir(src)]
        for bsdl_file in bsdl_files:
            bsdl = Bsdl(bsdl_file, dst)
            bsdl.add_to_urjtag()

    except (IndexError, FileNotFoundError):
        print("Usage: python3 injector.py <src> <dst>\n")
