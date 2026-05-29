async function load(){

const r=
await fetch("/stats")

const d=
await r.json()

v.innerText=d.vehicles

s.innerText=d.speed

r.innerText=d.red

re.innerText=d.reverse

p.innerText=d.plate

}

setInterval(
load,
1000
)

load()