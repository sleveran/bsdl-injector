# Urjtag's database is built of 3 levels - Manufacturer, Part Number, Stepping.
# Each level needs a ddf. ddfs follow the structure:
# relevant_chunk_of_idcode\tfolder_name\tdisplay_name 
# eq: 00100000\tstm\tSTMicroelectronics

# SYNOPSIS: injector.py <src>
# src - folder with bsdl files in it

# Script flow:
# extract idcode and entity_name defined in .bsdl/.bsd file:
# check if manufacturer_id is in MANUFACTURERS, if not - add it.
# the injector will automatically name manufacturers according to the attached JEP106 table
# the part will be named according to entity definition name / file's name.
# stepping of part will be added only if it is clearly stated in file (not XXXX)
import re
import os
import subprocess

class Bsdl():
    urjtag_dir = "./urjtag_database"
    urjtag_manufacturers_dir = f"{urjtag_dir}/MANUFACTURERS"
    jedec_manufacturers_dir = "manufacturers"
    injector_log_f = "./injector.log"

    def __init__(self, bsdl_directory: str):
        try:
            self.directory = bsdl_directory
            self._is_valid()
            self.idcode = ''
            self.entity_name = ''    
            with open(self.directory, 'r') as bsdl_fd:
                self.content = bsdl_fd.read()
            self._extract_idcode()
            self._extract_entity_name()
            self._extract_manufacturer_name()
            self._define_urjtag_directories()

        except subprocess.CalledProcessError:
            with open(self.injector_log_f, 'a') as log:
                log.write(f"{self.directory}, invalid bsdl file\n")

    def _extract_idcode(self):
        """extract and define the entity's idcode""" 
        idcode_re = re.compile("attribute IDCODE_REGISTER .* \"1\";", re.DOTALL)
        self.idcode = re.search(idcode_re, self.content)[0].split("\n")
        self.version_number, self.part_number, self.manufacturer_id = [field.split('\"')[1] for field in self.idcode[1:4]]
        self.idcode = self.version_number.upper() + self.part_number + self.manufacturer_id
    
    def _extract_entity_name(self):
        """extract and define the entity's name"""
        entity_declaration = re.search("entity .* is", self.content)
        self.entity_name = entity_declaration[0].split()[1].lower()
    
    def _extract_manufacturer_name(self):
        """extract and define the manufacturer name"""
        if self._is_urjtag_manufacturer():
            with open(self.urjtag_manufacturers_dir, 'r') as urjtag_manufacturers_fd:
               urjtag_manufacturers = urjtag_manufacturers_fd.readlines() 
            for manufacturer in urjtag_manufacturers:
                if self.manufacturer_id in manufacturer:
                    self.manufacturer_name = manufacturer.split('\t')[1].lower()
        else:
            with open(self.jedec_manufacturers_dir ,'r') as jedec_manufacturers_fd:
                jedec_manufacturers = jedec_manufacturers_fd.readlines()
            for manufacturer in jedec_manufacturers:
                if self.manufacturer_id in manufacturer:
                    self.manufacturer_name = manufacturer.strip().split()[-1].lower()
   
    def _define_urjtag_directories(self):
        self.manufacturer_dir = f"{self.urjtag_dir}/{self.manufacturer_name}"
        self.part_dir = f"{self.manufacturer_dir}/{self.entity_name}"
        self.parts_f = f"{self.manufacturer_dir}/PARTS"
        self.steppings_f = f"{self.part_dir}/STEPPINGS"

    def _add_urjtag_manufacturer(self):
        """add Bsdl.manufacturer_id to urjtag's manufacturer ddf, and creates the manufacturer's folder"""
        # update MANUFACTURERS ddf
        with open(self.urjtag_manufacturers_dir, 'a') as urjtag_manufacturers_fd:
            urjtag_manufacturers_fd.write(f"{self.manufacturer_id}\t{self.manufacturer_name}\t{self.manufacturer_name.capitalize()}\n")    

        # create manufacturer folder and PARTS file
        os.mkdir(self.manufacturer_dir)
        with open(self.parts_f, 'w') as urjtag_parts_fd:
           urjtag_parts_fd.write("# PARTS file created by bsdl-injector.py\n")

    def _add_urjtag_part(self):
        """add Bsdl.entity_name to urjtag's part ddf, and creates the part's folder"""
        # update PARTS ddf
        with open(self.parts_f, 'a') as urjtag_parts_fd:
            urjtag_parts_fd.write(f"{self.part_number}\t{self.entity_name}\t{self.entity_name.upper()}\n")

        # create part folder and STEPPINGS file
        os.mkdir(self.part_dir)
        with open(self.steppings_f, 'a') as urjtag_steppings_fd:
            urjtag_steppings_fd.write("# STEPPINGS file created by bsdl-injector.py\n")    
    
    def _add_urjtag_stepping(self):
        """add part stepping to urjtag's stepping ddf"""
        with open(self.steppings_f, 'a') as steppings_fd: 
            if not 'X' in self.version_number and self._is_urjtag_stepping(self.version_number):
                steppings_fd.write(f"{self.version_number}\t{self.entity_name}\t{self.version_number:}\n")

            else:
                steppings_re = re.compile(self.version_number.replace("X", "[0-1]{1}")) # 'x' can be matched by 1 or 0
                for stepping in range(0, 16):     
                    if re.match(steppings_re, f"{stepping:04b}") and not self._is_urjtag_stepping(f"{stepping:04b}"):
                        steppings_fd.write(f"{stepping:04b}\t{self.entity_name}\t{stepping:04b}\n")


    def _is_urjtag_manufacturer(self) -> bool:
        """returns True if manufacturer_id exists in urjtag's database, otherwise returns False"""
        with open(self.urjtag_manufacturers_dir, 'r') as urjtag_manufacturers_fd:
            urjtag_manufacturers = urjtag_manufacturers_fd.read()
        return True if self.manufacturer_id in urjtag_manufacturers else False 
    
    def _is_urjtag_part(self) -> bool:
        """returns True if part exists in urjtag's database, otherwise returns False"""
        with open(self.parts_f, 'r') as urjtag_parts_fd:
            urjtag_parts = urjtag_parts_fd.read()
        return True if self.entity_name in urjtag_parts else False

    def _is_urjtag_stepping(self, stepping) -> bool:
        """returns True if part's stepping exists in urjtag's database, otherwise returns False"""
        with open(self.steppings_f, 'r') as urjtag_steppings_fd:
            urjtag_steppings = urjtag_steppings_fd.read()
        return True if stepping in urjtag_steppings else False

    def _is_valid(self) -> bool:
        """raise subprocess.CalledProcessError if bsdl file is invalid"""
        subprocess.run(["bsdl2jtag", self.directory, "/dev/null"], check=True)
       
    def _copy_bsdl(self):
        subprocess.run(["cp", self.directory, f"{self.part_dir}/{self.entity_name}"], check=True)    

    def add_to_urjtag(self):
        """add bsdl to urjtag database"""
        if not self._is_urjtag_manufacturer():
            self._add_urjtag_manufacturer()
        if not self._is_urjtag_part():
            self._add_urjtag_part()
        self._add_urjtag_stepping()
        self._copy_bsdl()
        with open(self.injector_log_f, 'a') as log:
            log.write(f"{self.directory}, added successfully\n")
       


# new bsdl file
bsdl = Bsdl("./test_bsdls/example.bsdl")
bsdl.add_to_urjtag()
