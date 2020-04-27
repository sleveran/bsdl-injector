import re
import os
import subprocess
import sys

class Ddf():
    """This class represents urjtag's directory-description-files"""
    def __init__(self, path: str):
        self.path = path
        with open(self.path, 'r') as fd:
            self.content = fd.readlines()

        self.directory = '/'.join(list(filter(None, self.path.split('/')))[:-1])
        self.directory_list = os.listdir(self.directory)
        self.comments = self._get_comments()
        self.definitions = self._get_definitions()
        self.folders = self._get_folders()
        self.invalid_folders = self._get_invalid_folders()

    def _get_comments(self):
        """
        Get comment lines from urjtag ddfs. 
        :param lines: list of text lines - content of urjtag ddf file read with readlines()
        :return: list of comment lines
        """
        return [line for line in self.content if self._is_comment(line)]
        
    def _get_definitions(self):
        """
        Get definition lines from urjtag ddfs. 
        :param lines: list of text lines - content of urjtag ddf file read with readlines()
        :return: list of definition lines
        """
        return [line for line in self.content if self._is_definition(line)]

    @staticmethod
    def _is_comment(line: str) -> bool:
        """receives a text line, returns True if line starts with '#', otherwise returns False"""
        return True if line.startswith('#') else False

    @staticmethod
    def _is_definition(line: str) -> bool:
        """receives a text line, returns True if line follows the regex pattern .*\t.*\t.*"""
        return True if re.search(".*\t.*\t.*", line) else False

    def _get_folders(self) -> list:
        """returns all folder names in ddf"""
        return [line.split('\t')[1].strip() for line in self.definitions]
    
    def _get_invalid_folders(self):
        """returns folders mentioned in urjtag's ddf, but have no corresponding folder"""
        return [folder for folder in self.folders if folder not in self.directory_list]

    def clean(self):
        """Clean ddf file, remove definition lines that have no corresponding folders"""
        clean_ddf_content = [line for line in self.definitions if not line.split('\t')[1].strip() in self.invalid_folders]
        for line in clean_ddf_content:
            with open(self.path, 'w') as ddf:
                ddf.writelines(self.comments + clean_ddf_content)

class Bsdl():
    def __init__(self, path: str, dst: str):
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

        # read and save bsdl content
        # decoding errors are ignored since a few companies put special encoded characters into the their bsdls, utf-8 works for most part.
        with open(self.path, 'r', errors='ignore') as bsdl_fd:
            self.content = bsdl_fd.read()

        # get bsdl information
        self._get_idcode()

        self.manufacturer_name = self._get_manufacturer_name()
        self.manufacturer_path = f"{self.dst}/{self.manufacturer_name}/"
        self.urjtag_parts_f = f"{self.manufacturer_path}/PARTS"

        self._get_part_name()
        self.part_path = f"{self.manufacturer_path}/{self.part_name}/"
        self.urjtag_steppings_f = f"{self.part_path}/STEPPINGS"

    def _get_manufacturer_name(self) -> str:
        """get manufacturer name from urjtag's database or JEP106"""
        # get manufacturer name used in urjtag's database if it already exists
        if self._is_urjtag_manufacturer():
            with open(self.urjtag_manufacturers_f, 'r') as urjtag_manufacturers_fd:
               urjtag_manufacturers = urjtag_manufacturers_fd.read() 
            manufacturer = re.search(f".*{self.manufacturer_id}.*", urjtag_manufacturers).group()
            manufacturer = manufacturer.split('\t')[1]

        # get manufacturer name from jedec's jep106, in case urjtag's database doesn't have it
        else:
            with open(self.jedec_manufacturers_path ,'r') as jedec_manufacturers_fd:
                jedec_manufacturers = jedec_manufacturers_fd.read()
            manufacturer = re.search(f".*{self.manufacturer_id}.*", jedec_manufacturers).group()
            manufacturer = manufacturer[len(self.manufacturer_id):].strip().lower()
        return manufacturer

    def _get_part_name(self):
        """get entity's name from bsdl file"""
        # get part name used in urjtag's database if it already exists
        if self._is_urjtag_part():
            with open(self.urjtag_parts_f, 'r') as urjtag_parts_fd:
                urjtag_parts = urjtag_parts_fd.readlines()
            for part in urjtag_parts:
                if self.part_number in part:
                    self.part_name = part.split('\t')[1].lower()
                    
        # get part_name from bsdl's entity name 
        else:
            entity_declaration = re.search("entity .* is", self.content)
            self.part_name = entity_declaration[0].split()[1].lower()

    def _get_idcode(self):
        """get idcode from bsdl file"""
        idcode_re = re.compile("attribute IDCODE_REGISTER.*?;", re.DOTALL)
        idcode_declaration = re.search(idcode_re, self.content)[0]
        idcode_fragments = re.findall("\".*\"", idcode_declaration)
        self.idcode = ''.join(idcode_fragments).replace('\"', '')
        self.version_number, self.part_number, self.manufacturer_id = self.idcode[0:4], self.idcode[4:20], self.idcode[20:31]
    
    def _is_valid(self) -> bool:
        """raise subprocess.CalledProcessError if bsdl file is invalid"""
        subprocess.run(["bsdl2jtag", self.path, "/dev/null"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    def _copy(self):
        """copy bsdl file to urjtag's database"""
        subprocess.run(["cp", self.path, f"{self.part_path}/{self.part_name}"], check=True)    

    def _add_urjtag_manufacturer(self):
        """update urjtag's MANUFACTURERS ddf. create manufacturer folder and PARTS file."""
        # update MANUFACTURERS ddf
        with open(self.urjtag_manufacturers_f, 'a') as urjtag_manufacturers_fd:
            urjtag_manufacturers_fd.write(f"{self.manufacturer_id}\t{self.manufacturer_name}\t\t{self.manufacturer_name.capitalize()}\n")    

        # create manufacturer folder and PARTS file
        os.mkdir(self.manufacturer_path)
        with open(self.urjtag_parts_f, 'a') as urjtag_parts_fd:
           urjtag_parts_fd.write("# added by injector.py\n")

    def _add_urjtag_part(self):
        """update urjtag's PARTS ddf. create part folder and STEPPINGS file."""
        # update PARTS ddf
        with open(self.urjtag_parts_f, 'a') as urjtag_parts_fd:
            urjtag_parts_fd.write(f"{self.part_number}\t{self.part_name}\t\t{self.part_name.upper()}\n")

        # create part folder and STEPPINGS file
        os.mkdir(self.part_path)
        with open(self.urjtag_steppings_f, 'a') as urjtag_steppings_fd:
            urjtag_steppings_fd.write("# added by injector.py\n")    
    
    def _add_urjtag_stepping(self, stepping: str):
        """add stepping to urjtag's stepping ddf"""
        with open(self.urjtag_steppings_f, 'a') as steppings_fd: 
            steppings_fd.write(f"{stepping}\t{self.part_name}\t\t{stepping}\n")

    def _is_urjtag_manufacturer(self) -> bool:
        """returns True if manufacturer_id exists in urjtag's database, otherwise returns False"""
        with open(self.urjtag_manufacturers_f, 'r') as urjtag_manufacturers_fd:
            urjtag_manufacturers = urjtag_manufacturers_fd.read()
        return True if self.manufacturer_id in urjtag_manufacturers else False 
    
    def _is_urjtag_part(self) -> bool:
        """returns True if part exists in urjtag's database, otherwise returns False"""
        with open(self.urjtag_parts_f, 'r') as urjtag_parts_fd:
            urjtag_parts = urjtag_parts_fd.read()
        return True if self.part_number in urjtag_parts else False

    def _is_urjtag_stepping(self, stepping: str) -> bool:
        """returns True if part's stepping exists in urjtag's database, otherwise returns False."""
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
        if steppings != None:
            self._copy()
            print(f"Successfully added {self.path}\n")

if __name__ == '__main__':
    try:
        src = sys.argv[1] # directory which contains bsdl files
        dst = "/usr/local/share/urjtag/" # default urjtag database path
        if len(sys.argv) >= 3: # destination folder, urjtag's database 
            dst = sys.argv[2]

        # create list of absolute paths to each file in src directory
        bsdl_files = [src + bsdl_file for bsdl_file in os.listdir(src)] 
        manufacturers = Ddf('./urjtag_database/MANUFACTURERS')
        manufacturers.clean()
        # add all bsdl files in src to urjtag's database
        for bsdl_file in bsdl_files:
            try:
                print(f"adding {bsdl_file}")
                bsdl = Bsdl(bsdl_file, dst)
                # bsdl.add_to_urjtag()

            except subprocess.CalledProcessError:
                print(f"Failed adding {bsdl_file}, corrupt/invalid bsdl file\n")

            except TypeError:
                print(f"No IDCODE in bsdl {bsdl_file}\n")

    except (IndexError, FileNotFoundError):
        print("Usage: python3 injector.py <src> <dst>\n")

    except PermissionError:
        print("PermissionError: injector.py missing sufficient r/w permissions to perform operations on urjtag's database\n")