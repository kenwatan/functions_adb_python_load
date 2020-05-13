CREATE TABLE funtest
( region varchar2(10),
  col1 number(4),
  col2 number(4),
  col3 number(4)
);

BEGIN
  DBMS_CLOUD.CREATE_CREDENTIAL(
    credential_name => 'DEF_CRED_NAME',
    username => '<OCI UserNAME>',
    password => '<Auth Token>'
  );
END;
/

create or replace procedure csvload (file_name in varchar2)
is
BEGIN
 DBMS_CLOUD.COPY_DATA(
    table_name =>'FUNTEST',
    credential_name =>'DEF_CRED_NAME',
    file_uri_list =>file_name,
    format => json_object('delimiter' value ',', 'skipheaders' value '1')
 );
END;

