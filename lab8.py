# ЧАСТЬ 1. Библиотеки, векторная математика и геометрия

import tkinter as tk
from tkinter import ttk
import math
import base64
import struct
import zlib

WIDTH = 640
HEIGHT = 480
BACKGROUND = (24, 28, 38)


def add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def mul(v, k):
    return (v[0] * k, v[1] * k, v[2] * k)


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0]
    )


def length(v):
    return math.sqrt(dot(v, v))


def normalize(v):
    size = length(v)
    if size < 1e-10:
        return (0.0, 0.0, 0.0)
    return mul(v, 1.0 / size)


def rotate_point(p, ax, ay, az):
    x, y, z = p

    cy, sy = math.cos(ax), math.sin(ax)
    y, z = y * cy - z * sy, y * sy + z * cy

    cx, sx = math.cos(ay), math.sin(ay)
    x, z = x * cx + z * sx, -x * sx + z * cx

    cz, sz = math.cos(az), math.sin(az)
    x, y = x * cz - y * sz, x * sz + y * cz

    return (x, y, z)


def make_mesh(name, vertices, faces, position, color, scale=1.0):
    fixed_faces = []
    for face in faces:
        a, b, c = [vertices[i] for i in face[:3]]
        normal = cross(sub(b, a), sub(c, a))
        center = mul(add(add(a, b), c), 1.0 / 3.0)
        oriented = tuple(reversed(face)) if dot(normal, center) < 0 else tuple(face)
        for i in range(1, len(oriented) - 1):
            fixed_faces.append((oriented[0], oriented[i], oriented[i + 1]))
    return {
        "name": name,
        "vertices": vertices,
        "faces": fixed_faces,
        "position": position,
        "color": color,
        "scale": scale
    }

# ЧАСТЬ 2. Создание объектов, преобразования и камера

def create_objects():
    cube_v = [
        (-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1),
        (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1)
    ]
    cube_f = [
        (0, 3, 2, 1), (4, 5, 6, 7),
        (0, 1, 5, 4), (3, 7, 6, 2),
        (0, 4, 7, 3), (1, 2, 6, 5)
    ]

    tetra_v = [
        (0, 1.25, 0), (-1, -0.8, -0.8),
        (1, -0.8, -0.8), (0, -0.8, 1)
    ]
    tetra_f = [(0, 1, 2), (0, 3, 1), (0, 2, 3), (1, 3, 2)]

    octa_v = [
        (0, 1.25, 0), (0, -1.25, 0),
        (1, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 0, -1)
    ]
    octa_f = [
        (0, 2, 4), (0, 4, 3), (0, 3, 5), (0, 5, 2),
        (1, 4, 2), (1, 3, 4), (1, 5, 3), (1, 2, 5)
    ]

    return [
        make_mesh("Куб", cube_v, cube_f, (-1.45, 0, 0), (65, 155, 235), 0.72),
        make_mesh("Тетраэдр", tetra_v, tetra_f, (1.35, 0, 0), (235, 145, 65), 0.82),
        make_mesh("Октаэдр", octa_v, octa_f, (0, 0.05, 1.35), (105, 205, 135), 0.68)
    ]


def transform_mesh(mesh, angles, global_scale):
    ax, ay, az = angles
    result = []
    scale = mesh["scale"] * global_scale
    for vertex in mesh["vertices"]:
        p = mul(vertex, scale)
        p = rotate_point(p, ax, ay, az)
        result.append(add(p, mesh["position"]))
    return result



def camera_basis(camera_position, target):
    forward = normalize(sub(target, camera_position))
    world_up = (0.0, 1.0, 0.0)
    right = normalize(cross(forward, world_up))
    if length(right) < 1e-8:
        right = (1.0, 0.0, 0.0)
    up = normalize(cross(right, forward))
    return right, up, forward


def to_camera(point, camera_position, basis):
    right, up, forward = basis
    relative = sub(point, camera_position)
    return (dot(relative, right), dot(relative, up), dot(relative, forward))


def project(point_camera):
    x, y, z = point_camera
    if z <= 0.08:
        return None
    focal = 430.0
    sx = int(WIDTH * 0.5 + focal * x / z)
    sy = int(HEIGHT * 0.5 - focal * y / z)
    return (sx, sy, z)


def edge_function(a, b, x, y):
    return (x - a[0]) * (b[1] - a[1]) - (y - a[1]) * (b[0] - a[0])


def shade_color(base, normal, light_direction):
    intensity = max(0.18, dot(normalize(normal), normalize(light_direction)))
    intensity = 0.28 + 0.72 * intensity
    return tuple(max(0, min(255, int(channel * intensity))) for channel in base)

# ЧАСТЬ 3. Отсечение нелицевых граней, растеризация и Z-буфер

def rasterize_triangle(frame, zbuffer, p0, p1, p2, color, use_zbuffer):
    x0, y0, z0 = p0
    x1, y1, z1 = p1
    x2, y2, z2 = p2

    area = edge_function((x0, y0), (x1, y1), x2, y2)
    if abs(area) < 1e-8:
        return

    min_x = max(0, min(x0, x1, x2))
    max_x = min(WIDTH - 1, max(x0, x1, x2))
    min_y = max(0, min(y0, y1, y2))
    max_y = min(HEIGHT - 1, max(y0, y1, y2))

    inv_z0, inv_z1, inv_z2 = 1.0 / z0, 1.0 / z1, 1.0 / z2

    for py in range(min_y, max_y + 1):
        for px in range(min_x, max_x + 1):
            w0 = edge_function((x1, y1), (x2, y2), px + 0.5, py + 0.5) / area
            w1 = edge_function((x2, y2), (x0, y0), px + 0.5, py + 0.5) / area
            w2 = 1.0 - w0 - w1

            if w0 >= -1e-7 and w1 >= -1e-7 and w2 >= -1e-7:
                reciprocal_depth = w0 * inv_z0 + w1 * inv_z1 + w2 * inv_z2
                if reciprocal_depth <= 0:
                    continue
                depth = 1.0 / reciprocal_depth
                index = py * WIDTH + px
                if not use_zbuffer or depth < zbuffer[index]:
                    zbuffer[index] = depth
                    frame[index] = color


def render_scene(objects, angles, global_scale, camera_position,
                 culling_enabled, zbuffer_enabled):
    frame = [BACKGROUND] * (WIDTH * HEIGHT)
    zbuffer = [float("inf")] * (WIDTH * HEIGHT)
    basis = camera_basis(camera_position, (0.0, 0.0, 0.0))
    light = normalize((-0.5, 0.8, -0.6))
    triangles = []

    for mesh in objects:
        world_vertices = transform_mesh(mesh, angles, global_scale)
        camera_vertices = [
            to_camera(v, camera_position, basis) for v in world_vertices
        ]

        for face in mesh["faces"]:
            wa, wb, wc = [world_vertices[i] for i in face[:3]]
            normal = cross(sub(wb, wa), sub(wc, wa))
            center = mul(add(add(wa, wb), wc), 1.0 / 3.0)

            view_direction = sub(camera_position, center)
            if culling_enabled and dot(normal, view_direction) <= 0:
                continue

            ca, cb, cc = [camera_vertices[i] for i in face[:3]]
            pa, pb, pc = project(ca), project(cb), project(cc)
            if pa is None or pb is None or pc is None:
                continue

            color = shade_color(mesh["color"], normal, light)
            average_depth = (pa[2] + pb[2] + pc[2]) / 3.0
            triangles.append((average_depth, pa, pb, pc, color))

    if not zbuffer_enabled:
        triangles.sort(key=lambda item: item[0], reverse=True)

    for _, pa, pb, pc, color in triangles:
        rasterize_triangle(frame, zbuffer, pa, pb, pc, color, zbuffer_enabled)

    raw_image = bytearray()
    for y in range(HEIGHT):
        raw_image.append(0)
        start = y * WIDTH
        for x in range(WIDTH):
            raw_image.extend(frame[start + x])

    def png_chunk(chunk_type, data):
        chunk = chunk_type + data
        crc = zlib.crc32(chunk) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + chunk + struct.pack(">I", crc)

    png_data = bytearray(b"\x89PNG\r\n\x1a\n")
    png_data.extend(png_chunk(
        b"IHDR", struct.pack(">2I5B", WIDTH, HEIGHT, 8, 2, 0, 0, 0)
    ))
    png_data.extend(png_chunk(b"IDAT", zlib.compress(bytes(raw_image))) )
    png_data.extend(png_chunk(b"IEND", b""))

    return base64.b64encode(bytes(png_data)).decode("ascii")

# Пользовательский интерфейс

class GraphicsLab:
    def __init__(self, root):
        self.root = root
        self.root.title("Лабораторная работа №8 — Удаление невидимых граней")
        self.root.resizable(False, False)

        self.objects = create_objects()
        self.image = None
        self.photo = None

        self.angle_x = tk.DoubleVar(value=20)
        self.angle_y = tk.DoubleVar(value=25)
        self.angle_z = tk.DoubleVar(value=0)
        self.scale = tk.DoubleVar(value=1.0)
        self.camera_angle = tk.DoubleVar(value=35)
        self.camera_height = tk.DoubleVar(value=2.2)
        self.camera_distance = tk.DoubleVar(value=7.0)
        self.culling = tk.BooleanVar(value=True)
        self.zbuffer = tk.BooleanVar(value=True)
        self.show_axes = tk.BooleanVar(value=False)

        self.build_interface()
        self.update_scene()

    def build_interface(self):
        main = ttk.Frame(self.root, padding=10)
        main.pack()

        self.canvas = tk.Canvas(
            main, width=WIDTH, height=HEIGHT,
            bg="#181c26", highlightthickness=1,
            highlightbackground="#596273"
        )
        self.canvas.grid(row=0, column=0, rowspan=20, padx=(0, 12))

        panel = ttk.Frame(main, width=260)
        panel.grid(row=0, column=1, sticky="n")
        panel.grid_propagate(False)

        ttk.Label(panel, text="Управление сценой",
                  font=("Arial", 12, "bold")).pack(anchor="w", pady=(0, 8))

        self.add_slider(panel, "Вращение X", self.angle_x, -180, 180)
        self.add_slider(panel, "Вращение Y", self.angle_y, -180, 180)
        self.add_slider(panel, "Вращение Z", self.angle_z, -180, 180)
        self.add_slider(panel, "Масштаб объектов", self.scale, 0.4, 1.5)

        ttk.Separator(panel).pack(fill="x", pady=8)
        ttk.Label(panel, text="Параметры камеры",
                  font=("Arial", 11, "bold")).pack(anchor="w")
        self.add_slider(panel, "Орбита камеры", self.camera_angle, 0, 360)
        self.add_slider(panel, "Высота камеры", self.camera_height, 0.5, 5.0)
        self.add_slider(panel, "Расстояние камеры", self.camera_distance, 4, 12)

        ttk.Separator(panel).pack(fill="x", pady=8)
        ttk.Checkbutton(
            panel, text="Отсечение нелицевых граней",
            variable=self.culling, command=self.update_scene
        ).pack(anchor="w", pady=3)
        ttk.Checkbutton(
            panel, text="Использовать Z-буфер",
            variable=self.zbuffer, command=self.update_scene
        ).pack(anchor="w", pady=3)

        ttk.Button(panel, text="Сбросить параметры",
                   command=self.reset).pack(fill="x", pady=(12, 5))
        ttk.Button(panel, text="Вращать автоматически",
                   command=self.toggle_animation).pack(fill="x", pady=3)

        self.status = ttk.Label(panel, text="Готово", wraplength=245)
        self.status.pack(anchor="w", pady=(12, 0))

        ttk.Label(
            panel,
            text="Объекты: куб, тетраэдр и октаэдр.\n"
                 "Все вычисления и закраска выполняются программно.",
            wraplength=245, justify="left"
        ).pack(anchor="w", pady=(12, 0))

    def add_slider(self, parent, label, variable, low, high):
        block = ttk.Frame(parent)
        block.pack(fill="x", pady=3)
        ttk.Label(block, text=label).pack(anchor="w")
        slider = ttk.Scale(
            block, from_=low, to=high, variable=variable,
            command=lambda value: self.update_scene()
        )
        slider.pack(fill="x")

    def get_camera_position(self):
        angle = math.radians(self.camera_angle.get())
        distance = self.camera_distance.get()
        height = self.camera_height.get()
        return (
            distance * math.sin(angle),
            height,
            distance * math.cos(angle)
        )

    def update_scene(self):
        angles = (
            math.radians(self.angle_x.get()),
            math.radians(self.angle_y.get()),
            math.radians(self.angle_z.get())
        )
        camera_position = self.get_camera_position()

        encoded = render_scene(
            self.objects, angles, self.scale.get(), camera_position,
            self.culling.get(), self.zbuffer.get()
        )
        self.photo = tk.PhotoImage(data=encoded, format="PNG")
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, image=self.photo, anchor="nw")

        mode = "Z-буфер включён" if self.zbuffer.get() else "Z-буфер выключен"
        cull = "отсечение включено" if self.culling.get() else "отсечение выключено"
        self.status.config(text=f"{mode}\n{cull}\nКамера: {tuple(round(v, 2) for v in camera_position)}")

    def reset(self):
        self.angle_x.set(20)
        self.angle_y.set(25)
        self.angle_z.set(0)
        self.scale.set(1.0)
        self.camera_angle.set(35)
        self.camera_height.set(2.2)
        self.camera_distance.set(7.0)
        self.culling.set(True)
        self.zbuffer.set(True)
        self.update_scene()

    def toggle_animation(self):
        if getattr(self, "animating", False):
            self.animating = False
            return
        self.animating = True
        self.animate()

    def animate(self):
        if not getattr(self, "animating", False):
            return
        self.angle_y.set((self.angle_y.get() + 2) % 360)
        self.camera_angle.set((self.camera_angle.get() + 0.8) % 360)
        self.update_scene()
        self.root.after(40, self.animate)


if __name__ == "__main__":
    window = tk.Tk()
    app = GraphicsLab(window)
    window.mainloop()
