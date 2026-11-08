"""New-task tests selected before any model use; not model-visible."""
HELPER=r'''
use super::store_metadata as m;
fn filled()->m::Bucket {
 let mut b=m::new_bucket("sample".into());
 for (key,state) in [("c",m::ObjectState::Active),("a",m::ObjectState::Active),("b",m::ObjectState::Archived)] {
  b=m::put_object(b,m::ObjectMeta {key:key.into(),size:7,checksum:vec![1,2],state});
 }
 b
}
'''


def goals(ident):
    if ident=='H03':body=r'''
#[test] fn archived_objects_are_not_retrievable(){
 let b=filled();assert!(m::get_object(b.clone(),"b".into()).is_err());
 assert!(m::get_object(b.clone(),"missing".into()).is_err());
 let a=m::get_object(b.clone(),"a".into()).unwrap();assert_eq!(a.key,"a");assert_eq!(a.size,7);
 let b=m::put_object(b,m::ObjectMeta {key:"a".into(),size:8,checksum:vec![],state:m::ObjectState::Archived});
 assert!(m::get_object(b,"a".into()).is_err());
}
'''
    else:body=r'''
#[test] fn nonnegative_pagination_never_overflows(){
 let b=filled();let keys=m::list_objects(b.clone());
 for (offset,limit) in [(0,i64::MAX),(1,i64::MAX),(2,i64::MAX),(3,i64::MAX),(i64::MAX,i64::MAX),(0,0)] {
  let start=(offset as usize).min(keys.len());
  let count=(limit as usize).min(keys.len()-start);
  assert_eq!(m::list_objects_page(b.clone(),offset,limit),keys[start..start+count].to_vec());
 }
}
'''
    return '#[cfg(test)] mod context_goal {\n'+HELPER+body+'}\n'


def regressions(ident):
    body=r'''
#[test] fn other_metadata_operations_survive(){
 let b=filled();assert_eq!(m::object_count(b.clone()),3);
 let keys=m::list_objects(b.clone());let mut sorted=keys.clone();sorted.sort();assert_eq!(sorted,vec!["a","b","c"]);
 assert_eq!(m::list_objects_page(b.clone(),0,2),keys[0..2].to_vec());
 assert_eq!(m::list_objects_page(b.clone(),1,1),keys[1..2].to_vec());
 assert!(m::list_objects_page(b.clone(),8,2).is_empty());
 assert_eq!(m::state_label(m::ObjectState::Archived),"archived");
 let a=m::get_object(b.clone(),"a".into()).unwrap();assert_eq!(a.checksum,vec![1,2]);
 assert!(m::get_object(b.clone(),"missing".into()).is_err());
 assert_eq!(m::object_count(m::delete_object(b,"a".into())),2);
}
'''
    if ident=='H04':body+=r'''
#[test] fn archived_lookup_is_unchanged_outside_pagination_task(){
 assert!(m::get_object(filled(),"b".into()).is_ok());
}
'''
    return '#[cfg(test)] mod context_regression {\n'+HELPER+body+'}\n'
