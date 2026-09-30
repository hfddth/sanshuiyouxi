const CACHE_VERSION='sanshuiyouxi-cn-stable-1';
const CORE_ASSETS=[
  './',
  './index.html',
  './styles.css?v=cn-stable-1',
  './agent-config.js?v=cn-stable-1',
  './app.js?v=cn-stable-1',
  './sample-script.json?v=cn-stable-1',
  './assets/maps/map-01.webp',
  './assets/maps/map-02.webp',
  './assets/maps/map-03.webp',
  './assets/maps/map-04.webp',
  './assets/maps/map-05.webp',
  './assets/landmarks/bridge.webp',
  './assets/landmarks/courtyard.webp',
  './assets/landmarks/dock.webp',
  './assets/landmarks/gate.webp',
  './assets/landmarks/mountain-pavilion.webp',
  './assets/landmarks/mountain-temple.webp',
  './assets/landmarks/tower.webp',
  './assets/landmarks/village.webp',
  './assets/landmarks/water-corridor.webp',
  './assets/landmarks/waterside-house.webp',
  './assets/characters/antagonist-steward.webp',
  './assets/characters/bamboo-guide.webp',
  './assets/characters/craftsman.webp',
  './assets/characters/elder-fisherman.webp',
  './assets/characters/elder-scholar.webp',
  './assets/characters/elder-woman.webp',
  './assets/characters/herbalist-woman.webp',
  './assets/characters/merchant.webp',
  './assets/characters/official-scholar.webp',
  './assets/characters/opera-musician.webp',
  './assets/characters/opera-woman.webp',
  './assets/characters/village-child.webp',
  './assets/characters/village-guard.webp',
  './assets/characters/water-spirit.webp',
  './assets/characters/young-female-scholar.webp',
  './assets/characters/young-male-guide.webp',
  './assets/characters/young-monk.webp'
];

self.addEventListener('install',event=>{
  event.waitUntil((async()=>{
    const cache=await caches.open(CACHE_VERSION);
    await Promise.allSettled(CORE_ASSETS.map(asset=>cache.add(asset)));
    await self.skipWaiting();
  })());
});

self.addEventListener('activate',event=>{
  event.waitUntil((async()=>{
    const keys=await caches.keys();
    await Promise.all(keys.filter(key=>key.startsWith('sanshuiyouxi-')&&key!==CACHE_VERSION).map(key=>caches.delete(key)));
    await self.clients.claim();
  })());
});

async function networkFirst(request,fallback){
  const cache=await caches.open(CACHE_VERSION);
  try{
    const response=await fetch(request);
    if(response.ok)cache.put(request,response.clone());
    return response;
  }catch(error){
    const cached=await cache.match(request)||fallback&&await cache.match(fallback);
    if(cached)return cached;
    throw error;
  }
}

async function cacheFirst(request){
  const cache=await caches.open(CACHE_VERSION);
  const cached=await cache.match(request);
  if(cached)return cached;
  const response=await fetch(request);
  if(response.ok)cache.put(request,response.clone());
  return response;
}

self.addEventListener('fetch',event=>{
  const request=event.request;
  if(request.method!=='GET')return;
  const url=new URL(request.url);
  if(url.origin!==self.location.origin)return;
  if(request.mode==='navigate'){
    event.respondWith(networkFirst(request,'./index.html'));
    return;
  }
  if(/\.(?:js|css|json|html)$/.test(url.pathname)){
    event.respondWith(networkFirst(request));
    return;
  }
  if(/\.(?:webp|png|jpe?g|svg|ico)$/.test(url.pathname))event.respondWith(cacheFirst(request));
});
