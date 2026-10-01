'use strict';
// Clay serializes this function into its page. It has no external closure.
module.exports=function(){
  var page=this;
  page.on(page.EVENTS.AFTER_BUILD,function(){
    var ids=page.meta.userData.ids,walkKeys=page.meta.userData.walkKeys,
      save=page.getItemById('save-preferences'),message=page.getItemById('validation-message'),
      location=page.getItemByMessageKey('LocationEnabled'),startup=page.getItemByMessageKey('NearbyStartup'),homeAction=page.getItemByMessageKey('HomeAction');
    function known(id){return ids.indexOf(Number(id))!==-1;}
    function validInteger(value,min,max){var n=Number(value);return value!==''&&isFinite(n)&&Math.floor(n)===n&&n>=min&&n<=max;}
    function validChoice(value,max){return (typeof value==='number'||(typeof value==='string'&&/^[0-9]+$/.test(value)))&&validInteger(value,0,max);}
    function validate(){
      var error='',seen={},id=Number(page.getItemByMessageKey('DefaultId').get());
      if(location.get())startup.enable();
      else {
        if(startup.get())startup.set(false);
        startup.disable();
      }
      if(id&&!known(id))error='Remove or replace the unavailable default boarding point.';
      for(var i=0;i<12;i+=1){id=Number(page.getItemByMessageKey('Favourite'+i).get());if(id){if(!known(id))error='Remove unavailable favourites before saving.';else if(seen[id])error='Each favourite must appear once. Choose None in its old slot when moving it.';seen[id]=true;}}
      var walks=0;
      walkKeys.forEach(function(key){var value=page.getItemByMessageKey(key).get();if(value!==''){walks+=1;if(!known(key.slice(4)))error='Clear walking times for unavailable boarding points.';else if(!validInteger(value,0,120))error='Walking times must be whole minutes from 0 to 120, or blank.';}});
      if(walks>12)error='Keep at most 12 saved walking allowances; clear unused fields.';
      if(!validInteger(page.getItemByMessageKey('Buffer').get(),0,30))error='Buffer must be whole minutes from 0 to 30.';
      if(!validChoice(page.getItemByMessageKey('TextSize').get(),2))error='Choose Standard, Large or Extra Large text.';
      if(!validChoice(page.getItemByMessageKey('Theme').get(),3))error='Choose one of the four themes.';
      if(!validChoice(homeAction.get(),2))error='Choose Keep, Save current phone location as home or Clear saved home.';
      else if(Number(homeAction.get())===1&&!location.get())error='Turn on phone location to save your current location as home. Clear remains available.';
      message.set(error||'Preferences are ready to save. Walking times apply only in Saved origin context.');
      if(error)save.disable();else save.enable();
    }
    ['DefaultId','Buffer','NearbyStartup','LocationEnabled','TextSize','Theme','HomeAction'].concat(walkKeys).forEach(function(key){page.getItemByMessageKey(key).on('change',validate);});
    for(var i=0;i<12;i+=1)page.getItemByMessageKey('Favourite'+i).on('change',validate);
    validate();
  });
};
