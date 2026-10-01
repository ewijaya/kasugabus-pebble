'use strict';
module.exports=function(catalog,snapshot,hasHome,homeStatus){
  var options=[{label:'None / open stop picker',value:'0'}],favourites=[],walks=[];
  catalog.forEach(function(p){options.push({label:p.label,value:String(p.id)});});
  if(snapshot){
    var seen={};catalog.forEach(function(p){seen[p.id]=true;});
    snapshot.favourites.concat([snapshot.defaultId]).forEach(function(id){if(id&&!seen[id]){options.push({label:'Unavailable boarding point #'+id+' — remove to save',value:String(id)});seen[id]=true;}});
  }
  for(var i=0;i<12;i+=1)favourites.push({type:'select',messageKey:'Favourite'+i,label:'Favourite '+(i+1),options:options,defaultValue:'0'});
  catalog.forEach(function(p){walks.push({type:'input',messageKey:'Walk'+p.id,label:p.label,defaultValue:'',description:'Minutes from your saved origin; blank means unset.',attributes:{type:'number',min:0,max:120,step:1}});});
  if(snapshot)Object.keys(snapshot.walks).forEach(function(id){if(!catalog.some(function(p){return p.id===Number(id);}))walks.push({type:'input',messageKey:'Walk'+id,label:'Unavailable boarding point #'+id,defaultValue:String(snapshot.walks[id]),description:'Clear this unavailable walking allowance to save.',attributes:{type:'number',min:0,max:120,step:1}});});
  return [
    {type:'heading',defaultValue:'KasugaBus'},
    {type:'text',defaultValue:'Scheduled buses. Choose operator and boarding direction. Set favourite slots in order; choose None to remove. Save at most 12 walking allowances; a blank walking time stays unset.'},
    {type:'section',items:[{type:'heading',defaultValue:'Usual stop'}, {type:'select',messageKey:'DefaultId',label:'Default boarding point',options:options,defaultValue:'0'}].concat(favourites)},
    {type:'section',items:[{type:'heading',defaultValue:'Saved origin walking times'}, {type:'input',messageKey:'Buffer',label:'Additional buffer (minutes)',defaultValue:'2',attributes:{type:'number',min:0,max:30,step:1}}, {type:'text',defaultValue:'These allowances apply only when you select Saved origin on the watch. At stop and Nearby do not reuse them.'}].concat(walks)},
    {type:'section',items:[{type:'heading',defaultValue:'Preferences'},
      {type:'toggle',messageKey:'AutoChecks',label:'Daily timetable check on launch',defaultValue:true},
      {type:'toggle',messageKey:'LocationEnabled',label:'Use phone location for Nearby',description:'Uses your phone’s location when you open Nearby or refresh it. No continuous tracking.',defaultValue:false},
      {type:'toggle',messageKey:'NearbyStartup',label:'Open Nearby on startup',description:'Open Nearby and request a location when KasugaBus starts.',defaultValue:false},
      {type:'text',defaultValue:'Your phone may also ask for location permission.'},
      {type:'text',id:'saved-home-availability',defaultValue:hasHome?'Saved home is available on this phone.':'No saved home on this phone.'},
      {type:'select',messageKey:'HomeAction',label:'Saved home',defaultValue:'0',description:'Be at your intended home before saving. Only Save current phone location as home requests a location; Keep and Clear do not. The location stays on this phone.',options:[{label:'Keep',value:'0'},{label:'Save current phone location as home',value:'1'},{label:'Clear saved home',value:'2'}]},
      {type:'text',defaultValue:homeStatus===0?'Saved home was saved.':homeStatus===9?'Saved home was cleared.':homeStatus===null||typeof homeStatus==='undefined'?'Saved home is a fixed reference for All Departures; it is separate from walking allowances.':'Saved home was not changed. '+({1:'The location was too imprecise.',2:'The location was stale.',3:'Location permission was denied.',4:'The location request timed out.',5:'Phone location or private storage was unavailable.',8:'Turn on phone location before saving.'}[homeStatus]||'Try again.')},
      {type:'select',messageKey:'TextSize',label:'Text size',defaultValue:'1',description:'Large is the default. Larger text wraps and shows fewer rows.',options:[{label:'Standard',value:'0'},{label:'Large',value:'1'},{label:'Extra Large',value:'2'}]},
      {type:'select',messageKey:'Theme',label:'Theme',defaultValue:'0',description:'Choose a dark or light background, with neon accents or plain high contrast.',options:[{label:'Neon Dark',value:'0'},{label:'Neon Light',value:'1'},{label:'High Contrast Dark',value:'2'},{label:'High Contrast Light',value:'3'}]},
      {type:'toggle',messageKey:'ReducedMotion',label:'Reduce motion',defaultValue:true}]},
    {type:'text',id:'validation-message',defaultValue:'Checking preferences…'},
    {type:'submit',id:'save-preferences',defaultValue:'Save preferences'}
  ];
};
