'use strict';
module.exports=function(catalog,snapshot){
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
      {type:'toggle',messageKey:'LocationEnabled',label:'Allow location on startup',defaultValue:false},
      {type:'toggle',messageKey:'NearbyStartup',label:'Nearby on startup',defaultValue:false},
      {type:'toggle',messageKey:'HighContrast',label:'High contrast',defaultValue:false},
      {type:'toggle',messageKey:'ReducedMotion',label:'Reduce motion',defaultValue:true}]},
    {type:'text',id:'validation-message',defaultValue:'Checking preferences…'},
    {type:'submit',id:'save-preferences',defaultValue:'Save preferences'}
  ];
};
