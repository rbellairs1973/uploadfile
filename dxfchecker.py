import sys
from enum import Enum

import ezdxf
from shapely.geometry import Point
from shapely.geometry.polygon import Polygon


class ResultStatus(Enum):
    PASS = 1
    FAIL = 2
    UNKNOWN = 3

class Result():
    def __init__(self, status):
        self.status = status
        self.msg = ""

def gettextinsertionpoint(doc, entity):

    x_offset = -doc.header.hdrvars['$EXTMIN'].value[0]
    y_offset = -doc.header.hdrvars['$EXTMIN'].value[1]

    return Point(entity.dxf.insert.x + x_offset, doc.header.hdrvars['$EXTMAX'].value[1] - entity.dxf.insert.y - y_offset)

def polygonfrompolyline(doc, entity):

    x_offset = -doc.header.hdrvars['$EXTMIN'].value[0]
    y_offset = -doc.header.hdrvars['$EXTMIN'].value[1]

    points = []
    for v in entity.vertices:
        point = (v.dxf.location.x + x_offset, doc.header.hdrvars['$EXTMAX'].value[1] - v.dxf.location.y - y_offset)
        points.append(point)

    #if entity.dxf.flags == 1:
    #    point = (entity.vertices[0].dxf.location.x + x_offset, doc.header.hdrvars['$EXTMAX'].value[1] - entity.vertices[0].dxf.location.y - y_offset)
    #    points.append(point)

    return Polygon(points)

def polygonfromlwpolyline(doc, entity):

    x_offset = -doc.header.hdrvars['$EXTMIN'].value[0]
    y_offset = -doc.header.hdrvars['$EXTMIN'].value[1]

    points = []
    vertices = entity.vertices()
    for v in vertices:
        point = (v[0] + x_offset, doc.header.hdrvars['$EXTMAX'].value[1] - v[1] - y_offset)
        points.append(point)

    #if entity.dxf.flags == 1:
    #    point = (entity.get_points()[0][0] + x_offset, doc.header.hdrvars['$EXTMAX'].value[1] - entity.get_points()[0][1] - y_offset)
    #    points.append(point)

    polygon = None
    if len(points) > 2:
        polygon = Polygon(points)

    return polygon

def checkuniqueworkspacenumbers(doc):
    result = Result(ResultStatus.PASS)
    print("Checking workspace numbers are unique:\n")

    numbers = []
    entities = doc.modelspace().groupby(dxfattrib="layer")
    if "Planon_workspace_number" in entities.keys():
        for entity in entities["Planon_workspace_number"]:
            if entity.dxftype() == "TEXT":
                numbers.append(entity.dxf.text)

    if len(set(numbers)) != len(numbers):
        result.status = ResultStatus.FAIL
        result.msg = "Non-unique workspace numbers found.\n"

        for number in numbers:
            if numbers.count(number) > 1:
                result.msg = result.msg + number + "\n"

    return result

def checkuniquespaceandzonenumbers(doc):

    result = Result(ResultStatus.PASS)
    print("Checking space numbers are unique:\n")

    numbers = []
    entities = doc.modelspace().groupby(dxfattrib="layer")
    if "Planon_space_number" in entities.keys():
        for entity in entities["Planon_space_number"]:
            if entity.dxftype() == "TEXT":
                numbers.append(entity.dxf.text)

    if len(set(numbers)) != len(numbers):
        result.status = ResultStatus.FAIL
        result.msg = "Non-unique space numbers found.\n"

        for number in numbers:
            if numbers.count(number) > 1:
                result.msg = result.msg + number + "\n"

    return result

def getlayerpolylines(doc, layer):

    x_offset = -doc.header.hdrvars['$EXTMIN'].value[0]
    y_offset = -doc.header.hdrvars['$EXTMIN'].value[1]

    entities = doc.modelspace().groupby(dxfattrib="layer")
    polylines = []
    if layer in entities.keys():
        space_layer = entities[layer]

        for entity in space_layer:
            points = []
            type = entity.dxftype()
            if type == 'POLYLINE':
                for v in entity.vertices:
                    point = (v.dxf.location.x + x_offset,
                             doc.header.hdrvars['$EXTMAX'].value[1] - v.dxf.location.y - y_offset)
                    points.append(point)

                if entity.closed:
                    points.append(points[0])

            if type == 'LWPOLYLINE':
                vertices = entity.vertices()
                for v in vertices:
                    point = (v[0] + x_offset, doc.header.hdrvars['$EXTMAX'].value[1] - v[1] - y_offset)
                    points.append(point)

                if entity.closed:
                    points.append(points[0])

            polylines.append(points)

    return polylines

def checkoverlaps(doc):

    result = Result(ResultStatus.PASS)
    print("Checking for overlapping polylines:\n")

    msp = doc.modelspace()

    layers = msp.groupby(dxfattrib="layer")

    for layer in layers:
        if layer != "Planon_construction": # don't worry about this layer
            layer_status = ResultStatus.PASS

            polygons = []
            for entity in layers[layer]:
                type = entity.dxftype()
                polygon = None
                if type == 'POLYLINE':
                    polygon = polygonfrompolyline(doc, entity)

                if type == "LWPOLYLINE":
                    polygon = polygonfromlwpolyline(doc, entity)

                if polygon is not None:
                    polygons.append(polygon)

            for outer in polygons:
                for inner in polygons:
                    if inner is not outer:
                        if inner.overlaps(outer):
                            result.msg = result.msg + "Overlap detected in layer " + layer + "\n"
                            layer_status = ResultStatus.FAIL
                            break

                if layer_status == ResultStatus.FAIL:
                    break

            if result.status != ResultStatus.FAIL:
                result.status = layer_status

    return result

def checkfloorhasonepolyline(doc):

    result = Result(ResultStatus.PASS)
    print("Checking the Planon_floor polyline:\n")

    entities = doc.modelspace().groupby(dxfattrib="layer")
    if "Planon_floor" in entities.keys():
        numpolylines = 0
        for entity in entities["Planon_floor"]:
            type = entity.dxftype()
            if type == 'POLYLINE' or type == "LWPOLYLINE":
                numpolylines += 1

        if numpolylines == 1:
            result.msg = result.msg + "Planon_floor has 1 polyline.\n"
        else:
            result.msg = result.msg + "Planon_floor has " + str(numpolylines) + " polylines.\n"
            result.status = ResultStatus.FAIL
    else:
        result.msg = "Planon_floor has no polyline.\n"
        result.status = ResultStatus.FAIL

    return result

def checklayerspresent(doc):

    result = Result(ResultStatus.PASS)
    print("Checking layers present:\n")

    requiredlayers = ["Planon_floor", "Planon_space", "Planon_space_number", "Planon_workspace", "Planon_workspace_number", "Planon_zone", "Planon_construction"]

    for layer in requiredlayers:
        if layer.lower() not in doc.layers.entries:
            result.msg = result.msg + layer + ": NOT FOUND\n"
            result.status = ResultStatus.FAIL
        else:
            result.msg = result.msg + layer + ": FOUND\n"

    return result

def checknumentities(doc):

    MAX_ENTITIES = 15000

    result = Result(ResultStatus.PASS)
    print("Checking number of entities:\n")

    num = len(doc.entities)
    result.msg = str(num) + " entities.\n"

    if num > MAX_ENTITIES:
        result.status = ResultStatus.FAIL

    return result

def print_result(result):
    print(result.msg)
    if result.status == ResultStatus.PASS:
        print("PASS\n")
    if result.status == ResultStatus.FAIL:
        print("FAIL\n")

def check_workspaces_enclosed(doc):
    result = Result(ResultStatus.PASS)
    print("Checking workspaces are enclosed:\n")

    entities = doc.modelspace().groupby(dxfattrib="layer")
    space_numbers = []
    if "Planon_workspace_number" in entities.keys():
        for entity in entities["Planon_workspace_number"]:
            if entity.dxftype() == "TEXT":
                space_numbers.append((entity.dxf.text, gettextinsertionpoint(doc, entity)))

    result.msg = result.msg + str(len(space_numbers)) + " workspace numbers found.\n"

    space_polylines = getlayerpolylines(doc, "Planon_workspace")

    for number in space_numbers:
        for polyline in space_polylines:
            polygon = Polygon(polyline)
            if polygon.contains(number[1]):
                if polyline[0] != polyline[len(polyline)-1]:
                    result.status = ResultStatus.FAIL
                    result.msg = result.msg + "The polyline of workspace " + number[0] + " is not enclosed.\n"

    return result

def check_spaces_enclosed(doc):
    result = Result(ResultStatus.PASS)
    print("Checking spaces are enclosed:\n")

    entities = doc.modelspace().groupby(dxfattrib="layer")
    space_numbers = []
    if "Planon_space_number" in entities.keys():
        for entity in entities["Planon_space_number"]:
            if entity.dxftype() == "TEXT":
                space_numbers.append((entity.dxf.text, gettextinsertionpoint(doc, entity)))

    result.msg = result.msg + str(len(space_numbers)) + " space and zone numbers found.\n"

    space_polylines = getlayerpolylines(doc, "Planon_space")

    for number in space_numbers:
        for polyline in space_polylines:
            polygon = Polygon(polyline)
            if polygon.contains(number[1]):
                if polyline[0] != polyline[len(polyline)-1]:
                    result.status = ResultStatus.FAIL
                    result.msg = result.msg + "The polyline of space " + number[0] + " is not enclosed.\n"

    return result

def check_zones_enclosed(doc):
    result = Result(ResultStatus.PASS)
    print("Checking zones are enclosed:\n")

    entities = doc.modelspace().groupby(dxfattrib="layer")
    space_numbers = []
    if "Planon_space_number" in entities.keys():
        for entity in entities["Planon_space_number"]:
            if entity.dxftype() == "TEXT":
                space_numbers.append((entity.dxf.text, gettextinsertionpoint(doc, entity)))

    result.msg = result.msg + str(len(space_numbers)) + " space and zone numbers found.\n"

    space_polylines = getlayerpolylines(doc, "Planon_zone")

    for number in space_numbers:
        for polyline in space_polylines:
            polygon = Polygon(polyline)
            if polygon.contains(number[1]):
                if polyline[0] != polyline[len(polyline)-1]:
                    result.status = ResultStatus.FAIL
                    result.msg = result.msg + "The polyline of zone " + number[0] + " is not enclosed.\n"

    return result

def check_floor_enclosed(doc):
    result = Result(ResultStatus.PASS)
    print("Checking floor is enclosed:\n")

    floor_polyline = getlayerpolylines(doc, "Planon_floor")[0]

    if floor_polyline[0] != floor_polyline[len(floor_polyline)-1]:
        result.status = ResultStatus.FAIL
        result.msg = result.msg + "The floor polyline is not enclosed.\n"

    return result


def get_spaces(doc):

    msp = doc.modelspace()
    layers = msp.groupby(dxfattrib="layer")
    space_layer = layers["Planon_space"]
    space_number_layer = layers["Planon_space_number"]

    space_polylines = []
    for entity in space_layer:
        polyline = None

        if entity.dxftype() == "POLYLINE":
            polyline = polygonfrompolyline(doc, entity)

        if entity.dxftype() == "LWPOLYLINE":
            polyline = polygonfromlwpolyline(doc, entity)

        if polyline is not None:
            space_polylines.append(polyline)

    space_numbers = []
    for entity in space_number_layer:
        if entity.dxftype() == "TEXT":
            space_numbers.append((entity.dxf.text, gettextinsertionpoint(doc, entity)))

    spaces = []
    for number in space_numbers:
        for polyline in space_polylines:
            if polyline.contains(number[1]):
                spaces.append((polyline, number))

    return spaces

def check(filename):
    print("Reading dxf file: " + filename + "\n")
    doc = ezdxf.readfile(filename)

    print_result(checknumentities(doc))

    result = checklayerspresent(doc)
    print_result(result)

    if result.status == ResultStatus.PASS:
        print_result(checknumentities(doc))

        result = checkfloorhasonepolyline(doc)
        print_result(result)
        if result.status == ResultStatus.PASS:
            print_result(check_floor_enclosed(doc))

        print_result(check_spaces_enclosed(doc))
        print_result(check_workspaces_enclosed(doc))
        print_result(check_zones_enclosed(doc))
        print_result(checkoverlaps(doc))
        print_result(checkuniqueworkspacenumbers(doc))
        print_result(checkuniquespaceandzonenumbers(doc))



def main(argv):
    check(argv[0])


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    main(sys.argv[1:])

# See PyCharm help at https://www.jetbrains.com/help/pycharm/
