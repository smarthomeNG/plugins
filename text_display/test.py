from models.TextDisplayModel import TextDisplayModel


room_names = ["Jens", "Kino", "Bad EG", "Flur", "EWoZi", "Küche",
              "Johanna", "Bad OG", "SchlaZi", "Werkstatt", "Außen"]
prio_msg = ["A", "B"]
turbo = ["X"]
relevanz_maske = {
    "jens.temp.relevant": True,
    "kino.temp.relevant": True,
    "bad eg.temp.relevant": True,
    "flur.temp.relevant": True,
    "ewozi.temp.relevant": True,
    "küche.temp.relevant": True,
    "johanna.temp.relevant": True,
    "bad og.temp.relevant": True,
    "schlazi.temp.relevant": True,
    "werkstatt.temp.relevant": True,
    "außen.temp.relevant": True,
    "a.sehr.relevant": True,
    "b.sehr.relevant": True,
    "x.trbo.relevant": True,
}


def content_reader(prefix, suffix):
    return f"{prefix} {suffix}"


def append_msg_src(model, ring, room, suffix, path):
    rel_path = room.lower() + f".{path}.relevant"
    model.append_message_source_to_ring(ring,
                                        content_source_path=room.lower() +
                                        f".{path}.msg",
                                        content_source=lambda: content_reader(
                                            room, suffix),
                                        is_relevant_path=rel_path,
                                        is_relevant=lambda: relevanz_maske[rel_path])


def fill_model(model):
    for room in room_names:
        append_msg_src(model, "fenster", room, "20,3 C", "temp")
    for room in prio_msg:
        append_msg_src(model, "prio", room, "ist wichtig", "sehr")
    for room in turbo:
        append_msg_src(model, "turbo", room, "ist turbo", "trbo")

    return model


model = TextDisplayModel()

model.append_message_sink_to_rings(
    "sink_key", ["prio", "fenster", "oswald"], "Banana")
model.append_message_sink_to_overruling_rings("sink_key", ["turbo"])

model = fill_model(model)

# for k in relevanz_maske.keys():
#    relevanz_maske[k] = False

# relevanz_maske["jens.temp.relevant"] = True
# relevanz_maske["x.trbo.relevant"] = True


# for i in range(60):
#     print(model.tick_sink("sink_key"))
for k in relevanz_maske.keys():
    relevanz_maske[k] = False
    model.update_source_relevance(k)

# for i in range(20):
#     print(model.tick_sink("sink_key"))
relevanz_maske["jens.temp.relevant"] = True
model.update_source_relevance("jens.temp.relevant")
# relevanz_maske["x.trbo.relevant"] = True
model.update_source_relevance("x.trbo.relevant")
# for i in range(40):
#     print(model.tick_sink("sink_key"))


print(model.dump_sink("sink_key"))
