"""Surface-mesh a STEP file to JSON {p: [x,y,z,...], t: [i,j,k,...]} for the viewer."""
import json, sys, gmsh
src, dst, size = sys.argv[1], sys.argv[2], float(sys.argv[3])
gmsh.initialize(); gmsh.option.setNumber("General.Terminal", 0)
gmsh.model.occ.importShapes(src); gmsh.model.occ.synchronize()
gmsh.option.setNumber("Mesh.MeshSizeMin", size * 0.2); gmsh.option.setNumber("Mesh.MeshSizeMax", size)
gmsh.model.mesh.generate(2)
tags, coords, _ = gmsh.model.mesh.getNodes()
index = {int(t): i for i, t in enumerate(tags)}
tris = []
for et, _, nodes in zip(*gmsh.model.mesh.getElements(2)[:3]):
    if et == 2:
        tris += [index[int(n)] for n in nodes]
json.dump({"p": [round(c, 2) for c in coords], "t": tris}, open(dst, "w"))
print(len(tags), len(tris) // 3)
