from mergexp import *

net = Network('Web-DB-Lab', addressing==ipv4, routing==static)

# Nodes
attacker = net.node('attacker', image=='kali', proc.cores>=8, memory.capacity>=gb(32))
webserver = net.node('webserver', image=='2404', proc.cores==2, memory.capacity==gb(4))
dbserver = net.node('dbserver', image=='2404', proc.cores==2, memory.capacity==gb(4))

# External network (DMZ): attacker <-> webserver
external = net.connect([attacker, webserver])
external[attacker].socket.addrs  = ip4('10.0.0.1/24')
external[webserver].socket.addrs = ip4('10.0.0.2/24')

# Internal network: webserver <-> dbserver
internal = net.connect([webserver, dbserver])
internal[webserver].socket.addrs = ip4('10.0.1.1/24')
internal[dbserver].socket.addrs  = ip4('10.0.1.2/24')

experiment(net)
