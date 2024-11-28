#
# Prototype of a class for handling AZ- and EL-correction table
class Correction_table:
    def __init__(self, file_path: str):
        """
        Konstruktor, som indlæser data fra en file og opretter en liste.
        
        :param file_path: Sti til fil
        """
        self.data_list = self._load_file(file_path)

    def _load_file(self, file_path: str) -> list:
        """
        Privat metode til at læse data fra en fil og gemme den som en liste af linjer.
        
        :param file_path: Sti til filen der skal læses
        :return: En liste med data fra filen
        """
        data = []
        try:
            with open(file_path, 'r') as file:
                for line in file:
                    # Fjern newline-tegn og del linjen på semikolon
                    parts = line.strip().split(";")
                    # Konverter til floats og tilføj som tuple til data-listen
                    if float(parts[0]) == 0.0:
                        float_triple = (float(parts[0]), float(parts[1]), float(parts[0]))
                    else:
                        float_triple = (float(parts[0]), float(parts[1]), float(parts[0]) + float(parts[1]))
                    data.append(float_triple)
            return data
        except FileNotFoundError:
            print(f"Fil ikke fundet: {file_path}")
            return []
        except ValueError:
            print(f"Ugyldigt format i filen: {file_path}")
            return []


    def interpolate_sink(self, target_x: float, data_list: list) -> tuple:
        """
        K3NG Mega rotor controller svarer til "sink" og er down-stream, samt modtager kommandoer fra Set(P)
        Interpolerer for en given x-værdi i data_list og returnerer det tilsvarende (x, y) par.
        
        :param target_x: x-værdien at interpolere for
        :param data_list: Listen af (x, y) tuples hvor interpolation skal udføres
        :return: En tuple (target_x, interpoleret_y) eller None hvis x er udenfor intervallet
        """
        for i in range(len(data_list) - 1):
            x1, y1, z1 = data_list[i]
            x2, y2, z2 = data_list[i + 1]
            
            if x1 <= target_x <= x2:
                # Udfør lineær interpolation
                interpolated_y = y1 + (y2 - y1) * (target_x - x1) / (x2 - x1)
                return (target_x, interpolated_y)

        print(f"Værdien {target_x} er udenfor intervallet af data.")
        return None

    def interpolate_source(self, target_z: float, data_list: list) -> tuple:
        """
        SDRangel svare til "source" og er up-stream, samt styre kommandoer med Set(P)
        K3NG Mega svarer tilbage på "\?FC"-kommando, som bliver til z-værdi. Bliver til svar på Get(p).
        Interpolerer for en given z-værdi i data_list og returnerer det tilsvarende (z, y) par.

        :param target_z: z-værdien at interpolere for OG MÅ IKKE VÆRE 0 !!!
        :param data_list: Listen af (x, y, z) tuples hvor interpolation skal udføres
        :return: En tuple (target_z, interpoleret_y) eller None hvis z er udenfor intervallet
        """
        for i in range(len(data_list) - 1):
            x1, y1, z1 = data_list[i]
            x2, y2, z2 = data_list[i + 1]
            
            if z1 <= target_z <= z2:
                # Udfør lineær interpolation
                interpolated_y = y1 + (y2 - y1) * (target_z - z1) / (z2 - z1)
                return (target_z, interpolated_y)

        print(f"Værdien {target_z} er udenfor intervallet af data.")
        return None

# Eksempel på brug af klassen:
# az_coor_tbl = Correction_table("az_coor_table.txt")
#el_coor_tbl = Correction_table("el_coor_table.txt")
# print(az_coor_tbl.data_list)  # Data fra az-file
#print(el_coor_tbl.data_list)  # Data fra el-file
# print(az_coor_tbl.interpolate_sink(157, az_coor_tbl.data_list))  # Interpoler for x = 150 i data_list1
# print(az_coor_tbl.interpolate_source(156.55, az_coor_tbl.data_list))  # Interpoler for x = 150 i data_list1
#print(el_coor_tbl.interpolate_sink(13.8, el_coor_tbl.data_list))  # Interpoler for x = 11.5 i data_list1
#print(el_coor_tbl.interpolate_source(23.6, el_coor_tbl.data_list))  # Interpoler for x = 150 i data_list1
