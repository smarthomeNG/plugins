from lib.item import Items
items = Items.get_instance()
myfiller = "                                                            "
allItems = items.return_items()
for myItem in allItems:
    if not hasattr(myItem,'db'):
        continue
    mycount = myItem.db('countall', 0)
    print (myItem.property.name + myfiller[0:len(myfiller)-len(myItem.property.name)]+ ' - Anzahl Datensätze :'+str(mycount))
