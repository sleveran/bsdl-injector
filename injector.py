# UrJTAG has a database to keep track of known JTAG devices.
# The database is a folder tree, accompanied with directory description files (ddf).
# Folder tree's structure: MANUFACTURERS -> PARTS -> STEPPINGS
# eq: STMicroelectronics -> stm32l152 -> 0 (revision)
# Each level needs a ddf. ddfs follow the structure:
# relevant_chunk_of_idcode      folder_name     display_name 
# eq (MANUFACTURERS ddf): 00100000      stm     STMicroelectronics

# SYNOPSIS: injector.py <src>
# src - folder with bsdl files in it

# Script flow:
# extract idcode and entity_name defined in .bsdl/.bsd file:
# check if manufacturer_id is in MANUFACTURERS, if not - add it.
# the injector will automatically name manufacturers according to the attached JEP106 table
# the part will be named according to entity definition name / file's name.
# stepping of part will be added only if it is clearly stated in file (not XXXX)
import re

class Bsdl():
    urjtag_db_dir = "/usr/local/share/urjtag"
    urjtag_manufacturers_dir = f"{urjtag_db_dir}/MANUFACTURERS"
    jedec_manufacturers_dir = "manufacturers"

    def __init__(self, bsdl_directory: str):
        self.directory = bsdl_directory
        self.idcode = ''
        self.entity_name = ''    

        with open(self.directory, 'r') as bsdl_fd:
            self.content = bsdl_fd.read()
        self._extract_idcode()
        self._extract_entity_name()
        self._extract_manufacturer_name()

    def _extract_idcode(self):
        """extract and define the entity's idcode""" 
        idcode_re = re.compile("attribute IDCODE_REGISTER .* \"1\";", re.DOTALL)
        self.idcode = re.search(idcode_re, self.content).group().split("\n")
        self.version_number, self.part_number, self.manufacturer_id = [field.split('\"')[1] for field in self.idcode[1:4]]
        self.idcode = self.version_number + self.part_number + self.manufacturer_id
    
    def _extract_entity_name(self):
        """extract and define the entity's name"""
        entity_declaration = re.search("entity .* is", self.content)
        self.entity_name = entity_declaration.group().split()[1]
    
    def _extract_manufacturer_name(self):
        """extract and define the manufacturer name"""
        if self.is_urjtag_manufacturer():
            with open(self.urjtag_manufacturers_dir, 'r') as urjtag_manufacturers_fd:
               urjtag_manufacturers = urjtag_manufacturers_fd.readlines() 
            for manufacturer in urjtag_manufacturers:
                if self.manufacturer_id in manufacturer:
                    self.manufacturer_name = manufacturer.split('\t')[1]
        else:
            with open(self.jedec_manufacturers_dir ,'r') as jedec_manufacturers_fd:
                jedec_manufacturers = jedec_manufacturers_fd.readlines()
            for manufacturer in jedec_manufacturers:
                if self.manufacturer_id in manufacturer:
                    self.manufacturer_name = manufacturer.strip().split()[-1]

    def is_urjtag_manufacturer(self) -> bool:
        """returns True if manufacturer exists in urjtag's database, otherwise returns False"""
        with open(self.urjtag_manufacturers_dir, 'r') as urjtag_manufacturers_fd:
            urjtag_manufacturers = urjtag_manufacturers_fd.read()
        return True if self.manufacturer_id in urjtag_manufacturers else False 
    
    def is_urjtag_part(self) -> bool:
        """returns True if part exists in urjtag's database, otherwise returns False"""
        with open(f"{self.urjtag_db_dir + self.manufacturer_name.lower()}", 'r'):

# new bsdl file    
bsdl = Bsdl("example.bsdl")
print(bsdl.idcode)
print(bsdl.version_number)
print(bsdl.part_number)
print(bsdl.manufacturer_id)
print(bsdl.manufacturer_name)

"""
manufacturer = "00000100000" # 11-bit
part = "0110010000010100" # 16-bit
stepping = "0000" # 4-bit

with open("/usr/local/share/urjtag/MANUFACTURERS") as manufacturers_file:
    manufacturers = manufacturers_file.read()
with open(f"/usr/local/share/urjtag/{manufacturer}/PARTS") as parts_file:
    parts = parts_file.read()
with open(f"/usr/local/share/urjtag/{manufacturer}/{part}/STEPPINGS") as steppings_file:
    steppings = steppings_file.read()

if manufacturer in manufacturers:
    print(f"manufacturer: {manufacturer} already exists")

if part in parts:
    print(f"part: {part} already exists")

if stepping in steppings:
    print(f"stepping: {stepping} already exists")
"""
