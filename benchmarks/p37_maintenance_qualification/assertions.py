"""Trusted finite behavioral assertions; never a future model input or mount.

Authored by Codex independently of witness implementation, not human ground truth.
"""
BUILD_HELPER = r'''
fn pkg(name:&str,deps:&str,state:&str)->super::build_model::Package {
 super::build_model::parse_package(format!("name={}\nsource_hash=h\ndeps={}\nstate={}\noutput_hash=o\nprev_source_hash=h\ndep_outputs=\n",name,deps,state)).unwrap()
}
'''


def goals(ident):
    if ident == "MM04":
        body = r'''
#[test] fn incomplete_graphs_are_errors(){
 use super::build_model as m;
 for ps in [vec![pkg("a","a","BUILT")],vec![pkg("a","b","BUILT"),pkg("b","a","BUILT")],
            vec![pkg("x","","BUILT"),pkg("a","missing","BUILT")],vec![pkg("a","missing","BUILT")]] {
  assert!(m::topo_order(ps).is_err());
 }
}
'''
    elif ident == "MM05":
        body = r'''
#[test] fn unsuccessful_states_never_reuse(){
 use super::build_model as m;
 for state in ["PENDING","FAILED"] { assert!(m::needs_build(pkg("a","",state),"h".into(),vec![])); }
}
'''
    elif ident == "MM06":
        body = r'''
#[test] fn duplicate_names_are_scheduled_once(){
 use super::build_model as m;
 let ps=vec![pkg("b","a","BUILT"),pkg("b","a","BUILT"),pkg("c","a,a","BUILT"),pkg("b","a","BUILT"),pkg("d","b","BUILT")];
 assert_eq!(m::reverse_dependents(ps,"a".into()),vec!["b".to_string(),"c".to_string()]);
 let ps=vec![pkg("b","x","BUILT"),pkg("c","a","BUILT"),pkg("b","a","BUILT"),pkg("c","a","BUILT")];
 assert_eq!(m::reverse_dependents(ps,"a".into()),vec!["c".to_string(),"b".to_string()]);
}
'''
    else:
        return r'''
#[cfg(test)] mod p37_goal {
 #[test] fn xml_text_is_escaped(){
  use super::store_model as m;
  for (code,msg,wc,wm) in [("Bad<&","x > y & z","Bad&lt;&amp;","x &gt; y &amp; z"),
     ("&amp;","<tag>","&amp;amp;","&lt;tag&gt;"),("","雪&","","雪&amp;")] {
   let r=m::xml_error(409,code.into(),msg.into());
   assert_eq!(r.status,409);assert_eq!(r.content_type,"application/xml");
   assert_eq!(String::from_utf8(r.body).unwrap(),format!("<?xml version=\"1.0\"?><Error><Code>{}</Code><Message>{}</Message></Error>",wc,wm));
  }
 }
}
'''
    return "#[cfg(test)] mod p37_goal {\n" + BUILD_HELPER + body + "}\n"


def regressions(ident):
    if ident == "MM07":
        return r'''
#[cfg(test)] mod p37_regression {
 #[test] fn response_helpers_and_ordinary_errors_survive(){
  use super::store_model as m;
  let t=m::text_response(201,vec![65u8]); assert_eq!(t.status,201);assert_eq!(t.content_type,"text/plain");assert_eq!(t.body,vec![65u8]);assert_eq!(t.head_content_length,0);
  let x=m::xml_response(202,vec![66u8]);assert_eq!(x.status,202);assert_eq!(x.content_type,"application/xml");assert_eq!(x.body,vec![66u8]);
  let e=m::xml_error(400,"Bad".into(),"ordinary".into());assert_eq!(e.status,400);assert_eq!(e.head_content_length,0);
  assert_eq!(String::from_utf8(e.body).unwrap(),"<?xml version=\"1.0\"?><Error><Code>Bad</Code><Message>ordinary</Message></Error>");
 }
}
'''
    return "#[cfg(test)] mod p37_regression {\n" + BUILD_HELPER + r'''
#[test] fn valid_graph_order_and_helpers(){
 use super::build_model as m;
 assert_eq!(m::topo_order(vec![]).unwrap(),Vec::<String>::new());
 for ps in [vec![pkg("c","a","BUILT"),pkg("b","","BUILT"),pkg("a","","BUILT")],
            vec![pkg("a","","BUILT"),pkg("c","a","BUILT"),pkg("b","","BUILT")]] {
  assert_eq!(m::topo_order(ps).unwrap(),vec!["a".to_string(),"b".to_string(),"c".to_string()]);
 }
 assert!(m::has_cycle(vec![pkg("a","a","BUILT")]));
 assert!(!m::has_cycle(vec![pkg("a","","BUILT")]));
 assert!(m::vec_contains(vec!["a".into(),"b".into()],"b".into()));
 assert!(!m::vec_contains(vec![],"a".into()));
}
#[test] fn incremental_hash_and_dependency_semantics(){
 use super::build_model as m;
 for state in ["BUILT","CACHED"] {
  assert!(!m::needs_build(pkg("a","",state),"h".into(),vec![]));
  assert!(m::needs_build(pkg("a","",state),"changed".into(),vec![]));
 }
 let dep=pkg("d","","BUILT");
 let mut p=pkg("a","d","BUILT");
 assert!(m::needs_build(p.clone(),"h".into(),vec![dep.clone()]));
 p.dep_outputs.insert("d".into(),"o".into());
 assert!(!m::needs_build(p.clone(),"h".into(),vec![dep.clone()]));
 assert!(m::needs_build(p,"h".into(),vec![]));
 let mut p=pkg("a","d","CACHED");p.dep_outputs.insert("d".into(),"old".into());
 assert!(m::needs_build(p,"h".into(),vec![dep]));
}
#[test] fn direct_dependents_and_serialization(){
 use super::build_model as m;
 let ps=vec![pkg("c","a,a","BUILT"),pkg("b","a","BUILT"),pkg("d","b","BUILT")];
 assert_eq!(m::reverse_dependents(ps,"a".into()),vec!["c".to_string(),"b".to_string()]);
 assert_eq!(m::reverse_dependents(vec![],"a".into()),Vec::<String>::new());
 let p=m::parse_package(m::serialize_package(pkg("a","b,c","BUILT"))).unwrap();
 assert_eq!(p.name,"a");assert_eq!(p.deps,vec!["b".to_string(),"c".to_string()]);assert_eq!(m::state_label(p.state),"BUILT");
}
}
'''
