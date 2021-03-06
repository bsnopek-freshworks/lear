"""Fixture for getting, resetting, and clearing complete business data."""
import io
import logging
from http import HTTPStatus

from flask import Blueprint, jsonify, request, send_file
from legal_api import db
from legal_api.models.business import Business
from legal_api.models.office import OfficeType

from data_reset_tool.converter import ExcelConverter, ExcelWriter, JsonConverter


FIXTURE_BLUEPRINT = Blueprint('fixture', __name__)


@FIXTURE_BLUEPRINT.route('/api/fixture/import/', methods=['POST'], strict_slashes=False,
                         defaults={'business_identifier': ''})
@FIXTURE_BLUEPRINT.route('/api/fixture/import/<business_identifier>', methods=['POST'], strict_slashes=False)
def post(business_identifier):
    """Reset complete business data from spreadsheet."""
    args = request.args
    input_business_identifier = business_identifier

    # If we are rebuilding, drop the db and recreate from sqlalchemy
    rebuild = False
    rebuild_arg_name = 'rebuild'
    if rebuild_arg_name in args:
        rebuild_arg_value = args[rebuild_arg_name]
        rebuild_true_value = 'true'
        rebuild = rebuild_true_value == rebuild_arg_value
        if rebuild:
            logging.warning('Rebuilding database')
            db.drop_all()
            db.create_all()
            # Create lookup values
            registered_office_type = OfficeType(
                identifier=OfficeType.REGISTERED,
                description=OfficeType.REGISTERED
            )
            db.session.add(registered_office_type)
            records_office_type = OfficeType(
                identifier=OfficeType.RECORDS,
                description=OfficeType.RECORDS
            )
            db.session.add(records_office_type)
            db.session.commit()

    # Open the workbook from the uploaded file
    file_form_attribute_name = 'file'
    a_file = request.files[file_form_attribute_name]
    excel_converter = ExcelConverter()
    business_list = excel_converter.create_businesses_from_file(
        a_file, input_business_identifier, rebuild)

    json_converter = JsonConverter()
    return json_converter.convert_to_json(business_list)


@FIXTURE_BLUEPRINT.route('/api/fixture/export/<business_identifier>', methods=['GET'], strict_slashes=False,
                         defaults={'format': 'JSON'})
@FIXTURE_BLUEPRINT.route('/api/fixture/export/<business_identifier>/<format>', methods=['GET'], strict_slashes=False)
def get_all(business_identifier, format):  # pylint: disable=redefined-builtin
    """Get complete business data, output as spreadsheet."""
    business_list = []

    export_all_businesses_indicator = 'all_YES_IM_SURE'
    if business_identifier == export_all_businesses_indicator:
        business_list = Business.query.all()
    else:
        business = Business.find_by_identifier(business_identifier)
        if not business:
            return jsonify({'message': f'{business_identifier} not found'}), HTTPStatus.NOT_FOUND
        business_list.append(business)

    excel_format_name = 'excel'
    if format == excel_format_name:
        buf = __create_excel_file(business_list)
        excel_mimetype = 'application/vnd.ms-excel'
        return send_file(
            buf,
            as_attachment=True,
            attachment_filename='%s.xls' % business_identifier,
            mimetype=excel_mimetype
        )

    json_converter = JsonConverter()
    return json_converter.convert_to_json(business_list)


@FIXTURE_BLUEPRINT.route('/api/fixture/delete/<business_identifier>', methods=['DELETE'], strict_slashes=False)
def delete(business_identifier):
    """Delete complete business data."""
    input_business_identifier = business_identifier

    excel_converter = ExcelConverter()
    excel_converter.delete_business(input_business_identifier)

    return jsonify({})


def __create_excel_file(business_list):
    excel_writer = ExcelWriter()
    excel_object = excel_writer.convert_to_excel(business_list)
    buf = io.BytesIO()
    excel_object.save(buf)
    buf.seek(0)
    return buf
